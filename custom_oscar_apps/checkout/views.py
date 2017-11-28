import logging
import stripe
from decimal import Decimal as D
from collections import namedtuple
from django import http
from django.db.models import Q
from django.utils import six
from django.conf import settings
from django.core.urlresolvers import reverse, reverse_lazy, resolve
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.views import generic
from django.utils.translation import ugettext as _
from django.core.exceptions import ImproperlyConfigured
from oscar.core import prices
from oscar.core.compat import user_is_authenticated, get_user_model
from oscar.apps.checkout import views, mixins, session, \
    exceptions as checkout_exceptions, signals
from oscar.apps.payment import exceptions, models as payment_models
from oscar.core.loading import get_class, get_model
from custom_oscar_apps.checkout.forms import StripePaymentForm, PaymentMethodForm
from custom_oscar_apps.payment.methods import CARD_PAYMENT, WIRE_TRANSFER
from custom_oscar_apps.payment.repository import Repository as PaymentRepository

logger = logging.getLogger('stripe')

CheckoutSessionData = get_class('checkout.utils', 'CheckoutSessionData')
UnableToPlaceOrder = get_class('order.exceptions', 'UnableToPlaceOrder')
CommunicationEventType = get_model('customer', 'CommunicationEventType')
Order = get_model('order', 'Order')
Line = get_model('order', 'Line')
Dispatcher = get_class('customer.utils', 'Dispatcher')
ShippingRepository = get_class('shipping.repository', 'Repository')
FixedPriceShipping = get_class('shipping.methods', 'FixedPrice')
OrderEventHandler = get_class('order.processing', 'EventHandler')
OrderTotalCalculator = get_class('checkout.calculators', 'EschewBasketOrderTotalCalculator')
USSalesTax = get_class('partner.strategy', 'USStateWiseSalesTax')

# ===============
# Shipping method
# ===============


class ShippingMethodView(views.ShippingMethodView):
    """
    View for allowing a user to choose a shipping method.

    Shipping methods are largely domain-specific and so this view
    will commonly need to be subclassed and customised.

    The default behaviour is to load all the available shipping methods
    using the shipping Repository.  If there is only 1, then it is
    automatically selected.  Otherwise, a page is rendered where
    the user can choose the appropriate one.
    """
    def get_success_response(self):
        """
        We redirect to place an order. Order will be approved by admin
        and then the user will be allowed to enter payment details.
        """
        return redirect('checkout:post-paid-order')


class PlacePostPaidOrderView(mixins.OrderPlacementMixin, generic.TemplateView):
    """
    View for allowing a user to place a post paid order.

    These orders require admins to approve before payments are accepted.

    The view just shows a preview of the details collected along with
    the cart details, including shipping charge.
    """
    communication_type_code = 'ORDER_PLACED_ADMIN_ALERT'
    template_name = 'checkout/post_paid_preview.html'
    pre_conditions = [
        'check_basket_is_not_empty',
        'check_basket_is_valid',
        'check_user_email_is_captured',
        'check_shipping_data_is_captured'
    ]

    # this is always True.
    preview = True

    def get_success_url(self):
        return reverse('checkout:thank-you-post-paid-order')

    def render_preview(self, request, **kwargs):
        """
        Show a preview of the order.
        """
        self.preview = True
        ctx = self.get_context_data(**kwargs)
        return self.render_to_response(ctx)

    def get(self, request, *args, **kwargs):
        shipping_address = self.get_shipping_address(request.basket)
        self.sales_tax = USSalesTax(request.basket.currency, request.basket.total_excl_tax, shipping_address)

        return super(PlacePostPaidOrderView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        shipping_address = self.get_shipping_address(request.basket)
        self.sales_tax = USSalesTax(request.basket.currency, request.basket.total_excl_tax, shipping_address)
        # We use a custom parameter to indicate if this is an attempt to place
        # an order (normally from the preview page).  Without this,
        # we return a 400 bad request.
        if request.POST.get('action', '') == 'place_post_paid_order':
            return self.handle_place_order_submission(request)
        return http.HttpResponseBadRequest()

    def handle_place_order_submission(self, request):
        """
        Handle a request to place an order.

        This method is normally called after the customer has clicked "place
        order" on the preview page. It's responsible for (re-)validating any
        form information then building the submission dict to pass to the
        `submit` method.

        We do not have any form data to be validated at this point.
        """
        return self.submit(**self.build_submission())

    def get_taxes(self):
        return (self.sales_tax_info(),)

    def get_sales_taxinfo(self):
        return self.sales_tax.calculate()

    def sales_tax_info(self):
        tax_info = self.get_sales_taxinfo()
        if tax_info:
            title = self.sales_tax.name
            TaxInfo = namedtuple('TaxInfo', ['title', 'code', 'amount'])
            return TaxInfo(
                title=title,
                code=self.sales_tax.code,
                amount=tax_info.tax
            )

    def apply_tax_us_state_sales_tax(self, submission):
        """
        Method to apply US sales tax.
        These tax apply methods have one common pattern,
        apply_tax_<tax code>.
        """
        if submission['shipping_address'] and submission['shipping_method']:
            tax_info = self.get_sales_taxinfo()
            line_count = len(submission['basket'].all_lines())
            for line in submission['basket'].all_lines():
                # get the tax per line.
                tax_per_line = (tax_info.tax / line_count).quantize(D('0.01'))
                # get tax per product in each line.
                tax_per_product = (tax_per_line / line.quantity).quantize(D('0.01'))
                line.purchase_info.price.tax = tax_per_product

            # Recalculate order total to ensure we have a tax-inclusive total
            submission['order_total'] = self.get_order_totals(
                submission['basket'],
                submission['shipping_charge'])

    def build_submission(self, **kwargs):
        submission = super(PlacePostPaidOrderView, self).build_submission(
            **kwargs)

        taxes = self.get_taxes()
        for tax in taxes:
            getattr(self, 'apply_tax_%s' % tax.code)(submission)

        # set taxes in context so we can display them.
        submission['basket'].taxes = taxes

        return submission

    def submit(self, user, basket, shipping_address, shipping_method,  # noqa (too complex (10))
               shipping_charge, billing_address, order_total,
               payment_kwargs=None, order_kwargs=None):
        """
        Submit a basket for order placement.

        The process runs as follows:

         * Generate an order number
         * Freeze the basket so it cannot be modified any more (important when
           redirecting the user to another site for payment as it prevents the
           basket being manipulated during the payment process).
         * Save the order.

        :basket: The basket to submit.
        :payment_kwargs: None always. Because we do not accept payment at this point.
        :order_kwargs: Additional kwargs to pass to the place_order method
        """
        if payment_kwargs is None:
            payment_kwargs = {}
        if order_kwargs is None:
            order_kwargs = {}

        # Taxes must be known at this point
        assert basket.is_tax_known, (
            "Basket tax must be set before a user can place an order")
        assert shipping_charge.is_tax_known, (
            "Shipping charge tax must be set before a user can place an order")

        # We generate the order number first as this will be used
        # in payment requests (ie before the order model has been
        # created).  We also save it in the session for multi-stage
        # checkouts (eg where we redirect to a 3rd party site and place
        # the order on a different request).
        order_number = self.generate_order_number(basket)
        self.checkout_session.set_order_number(order_number)
        logger.info("Order #%s: beginning submission process for basket #%d",
                    order_number, basket.id)

        # Freeze the basket so it cannot be manipulated while the customer is
        # completing payment on a 3rd party site.  Also, store a reference to
        # the basket in the session so that we know which basket to thaw if we
        # get an unsuccessful payment response when redirecting to a 3rd party
        # site.
        self.freeze_basket(basket)
        self.checkout_session.set_submitted_basket(basket)
        try:
            return self.handle_order_placement(
                order_number, user, basket, shipping_address, shipping_method,
                shipping_charge, billing_address, order_total, **order_kwargs)
        except UnableToPlaceOrder as e:
            # It's possible that something will go wrong while trying to
            # actually place an order. We are safe here, since no payment is
            # actually taken.
            msg = six.text_type(e)
            logger.error("Order #%s: unable to place order - %s",
                         order_number, msg, exc_info=True)
            self.restore_frozen_basket()
            return self.render_preview(
                self.request, error=msg, **payment_kwargs)

    # Post-order methods
    # ------------------

    def handle_successful_order(self, order):
        """
        Handle the various steps required after an order has been successfully
        placed.

        Override this view if you want to perform custom actions when an
        order is submitted.
        """
        # Send an email to admins.
        self.send_order_alert_to_admins(order, self.communication_type_code)

        # Flush all session data
        self.checkout_session.flush()

        # Save order id in session so thank-you page can load it
        self.request.session['checkout_order_id'] = order.id

        response = http.HttpResponseRedirect(self.get_success_url())
        self.send_signal(self.request, response, order)
        return response

    def get_message_context(self, order):
        ctx = super(PlacePostPaidOrderView, self).get_message_context(order)
        ctx.update({
            'dashboard_order_link': self.request.build_absolute_uri(
                reverse(
                    'dashboard:order-detail',
                    args=(order.number,)
                )
            )
        })
        return ctx

    def send_order_alert_to_admins(self, order, code, **kwargs):
        ctx = self.get_message_context(order)
        try:
            event_type = CommunicationEventType.objects.get(code=code)
        except CommunicationEventType.DoesNotExist:
            # No event-type in database, attempt to find templates for this
            # type and render them immediately to get the messages.  Since we
            # have not CommunicationEventType to link to, we can't create a
            # CommunicationEvent instance.
            messages = CommunicationEventType.objects.get_and_render(code, ctx)
            event_type = None
        else:
            messages = event_type.get_messages(ctx)

        if messages and messages['body']:
            logger.info("Order #%s - sending %s messages to admins.", order.number, code)
            dispatcher = Dispatcher(logger)
            for admin in get_user_model().objects.filter(is_superuser=True):
                dispatcher.dispatch_direct_messages(admin.email, messages)
        else:
            logger.warning("Order #%s - no %s communication event type",
                           order.number, code)


# =========================
# Thank you Post Paid Order
# =========================

class PostPaidOrderThankYouView(views.ThankYouView):
    """
    Displays the 'thank you' page which summarises the order just submitted.
    """
    template_name = 'checkout/thank_you_post_paid_order.html'
    context_object_name = 'order'


# ==============
# Payment method
# ==============


class PaymentMethodView(session.CheckoutSessionMixin, generic.FormView):
    """
    View for a user to choose which payment method(s) they want to use.

    This would include setting allocations if payment is to be split
    between multiple sources. It's not the place for entering sensitive details
    like bankcard numbers though - that belongs on the payment details view.
    """
    pre_conditions = ['check_user_email_is_captured']
    skip_conditions = None
    template_name = 'checkout/payment_methods.html'
    form_class = PaymentMethodForm

    def check_user_owns_order(self, request):
        if not Order._default_manager.filter(
            Q(user=request.user) |
            Q(guest_email=self.checkout_session.get_guest_email()),
            pk=self.order.pk
        ).exists():
            raise checkout_exceptions.FailedPreCondition(
                url=reverse('customer:order-list'),
                message=_('You cannot make payment for Order #%s.' % self.order.number)
            )

    def check_order_is_approved(self, request, order):
        if order.status != settings.OSCAR_APPROVED_ORDER_STATUS:
            raise checkout_exceptions.FailedPreCondition(
                url=reverse('customer:order-list'),
                message=_(
                    (
                        "Order %s is in %s state. "
                        "Payment can be made only on orders in %s state."
                    ) % (order.number, order.status, settings.OSCAR_APPROVED_ORDER_STATUS)
                )
            )

    def check_order_has_nonzero_total(self, request, order):
        # Check to see if payment is actually required for this order.
        shipping_address = self.get_shipping_address(order)
        shipping_method = self.get_shipping_method(
            order, shipping_address)
        if shipping_method:
            shipping_charge = shipping_method.calculate(order.basket)
        else:
            # It's unusual to get here as a shipping method should be set by
            # the time this skip-condition is called. In the absence of any
            # other evidence, we assume the shipping charge is zero.
            shipping_charge = prices.Price(
                currency=order.basket.currency, excl_tax=D('0.00'),
                tax=D('0.00')
            )
        total = self.get_order_totals(order, shipping_charge)
        if total.excl_tax == D('0.00'):
            # if total price is Zero, then return to order page.
            # with message, that we don't allow orders without a total price.
            raise checkout_exceptions.FailedPreCondition(
                url=reverse('customer:order'),
                message=_(
                    (
                        "Total amount for Order %s is %s. "
                        "Payment can be made only on orders with a valid total amount."
                    ) % (order.number, float(total.excl_tax))
                )
            )

    def post(self, request, order_number, *args, **kwargs):
        self.order = get_object_or_404(Order, number=order_number)
        self.order.basket.strategy = request.strategy

        try:
            self.check_user_owns_order(request)
        except checkout_exceptions.FailedPreCondition as e:
            for message in e.messages:
                messages.warning(request, message)
            return http.HttpResponseRedirect(e.url)

        try:
            self.check_order_is_approved(request, self.order)
        except checkout_exceptions.FailedPreCondition as e:
            for message in e.messages:
                messages.warning(request, message)
            return http.HttpResponseRedirect(e.url)

        try:
            self.check_order_has_nonzero_total(request, self.order)
        except checkout_exceptions.FailedPreCondition as e:
            logger.error('Order #%s. Order Total is 0. Redirecting to Order page.', self.order.number)
            for message in e.messages:
                messages.warning(request, message)
            return http.HttpResponseRedirect(e.url)

        self._methods = self.get_available_payment_methods()
        return super(PaymentMethodView, self).post(request, order_number, *args, **kwargs)

    def get(self, request, order_number, *args, **kwargs):
        self.order = get_object_or_404(Order, number=order_number)
        self.order.basket.strategy = request.strategy

        try:
            self.check_user_owns_order(request)
        except checkout_exceptions.FailedPreCondition as e:
            for message in e.messages:
                messages.warning(request, message)
            return http.HttpResponseRedirect(e.url)

        try:
            self.check_order_is_approved(request, self.order)
        except checkout_exceptions.FailedPreCondition as e:
            for message in e.messages:
                messages.warning(request, message)
            return http.HttpResponseRedirect(e.url)

        try:
            self.check_order_has_nonzero_total(request, self.order)
        except checkout_exceptions.FailedPreCondition as e:
            logger.error('Order #%s. Order Total is 0. Redirecting to Order page.', self.order.number)
            for message in e.messages:
                messages.warning(request, message)
            return http.HttpResponseRedirect(e.url)

        self._methods = self.get_available_payment_methods()

        if len(self._methods) == 0:
            # No payment methods available.
            # redirect onto the next step.
            return self.get_success_response()

        elif len(self._methods) == 1:
            # Only one payment method - set this and redirect onto the next
            # step
            self.checkout_session.pay_by(self._methods[0].code)
            return self.get_success_response()

        # Must be more than one available payment method, we present them to
        # the user to make a choice.
        return super(PaymentMethodView, self).get(request, order_number, *args, **kwargs)

    def build_submission(self, **kwargs):
        """
        Return a dict of data that contains everything required for an order
        submission.  This includes payment details (if any).

        This can be the right place to perform tax lookups and apply them to
        the basket.
        """
        basket = kwargs.get('basket', self.request.basket)
        shipping_address = self.get_shipping_address(self.order)
        shipping_method = self.get_shipping_method(
            self.order, shipping_address)
        billing_address = self.get_billing_address(shipping_address)
        if not shipping_method:
            total = shipping_charge = None
        else:
            shipping_charge = shipping_method.calculate(basket)
            total = self.get_order_totals(
                self.order, shipping_charge=shipping_charge)
        submission = {
            'user': self.request.user,
            'basket': basket,
            'shipping_address': shipping_address,
            'shipping_method': shipping_method,
            'shipping_charge': shipping_charge,
            'billing_address': billing_address,
            'order_total': total,
            'order_kwargs': {},
            'payment_kwargs': {}}

        # If there is a billing address, add it to the payment kwargs as calls
        # to payment gateways generally require the billing address. Note, that
        # it normally makes sense to pass the form instance that captures the
        # billing address information. That way, if payment fails, you can
        # render bound forms in the template to make re-submission easier.
        if billing_address:
            submission['payment_kwargs']['billing_address'] = billing_address

        # Allow overrides to be passed in
        submission.update(kwargs)

        # Set guest email after overrides as we need to update the order_kwargs
        # entry.
        if (not user_is_authenticated(submission['user']) and
                'guest_email' not in submission['order_kwargs']):
            email = self.checkout_session.get_guest_email()
            submission['order_kwargs']['guest_email'] = email
        return submission

    def get_context_data(self, **kwargs):
        kwargs = super(PaymentMethodView, self).get_context_data(**kwargs)
        kwargs['methods'] = self._methods
        kwargs['order'] = self.order
        return kwargs

    def get_form_kwargs(self):
        kwargs = super(PaymentMethodView, self).get_form_kwargs()
        kwargs['methods'] = self._methods
        return kwargs

    def form_valid(self, form):
        # Save the code for the chosen payment method in the session
        # and continue to the next step.
        self.checkout_session.pay_by(form.cleaned_data['method_code'])
        return self.get_success_response()

    def form_invalid(self, form):
        messages.error(self.request, _("Your submitted payment method is not"
                                       " permitted"))
        return super(PaymentMethodView, self).form_invalid(form)

    def get_success_response(self):
        return redirect(reverse('checkout:payment-details', args=(self.order.number,)))

    def get_available_payment_methods(self):
        return PaymentRepository().get_payment_methods(
            order=self.order
        )

    def get_default_payment_method(self):
        try:
            return PaymentRepository().get_default_payment_method(
                order=self.order
            )
        except ImproperlyConfigured as e:
            UnknownPaymentMethod = namedtuple(
                'UnknownPaymentMethod',
                ['name', 'code']
            )
            return UnknownPaymentMethod(name='Unknown', code='unknown')

    def get_shipping_address(self, order):
        """
        Return the shipping address for this order.
        """
        if not order.basket.is_shipping_required():
            return None

        return order.shipping_address

    def get_shipping_method(self, order, shipping_address=None, **kwargs):
        """
        Return a fixed price shipping method instance from the
        shipping charges stored in the order.

        Shipping address can be used for validation.
        """
        return FixedPriceShipping(order.shipping_excl_tax, order.shipping_incl_tax)

    def get_order_totals(self, order, shipping_charge, **kwargs):
        """
        Returns the total for the order with and without tax
        """
        return OrderTotalCalculator(self.request).calculate(
            order, shipping_charge, **kwargs)


class PaymentDetailsView(views.PaymentDetailsView):
    pre_conditions = None
    skip_conditions = None

    form_class = StripePaymentForm

    # Default code for the email to send after successful payment.
    communication_type_code = 'ORDER_PAID'

    def get_pre_conditions(self, request):
        if self.preview:
            # The preview view needs to ensure payment information has been
            # correctly captured, according to the payment method.
            return [
                'check_user_email_is_captured',
                'check_user_owns_order',
                'check_payment_data_is_captured'
            ]
        return ['check_user_email_is_captured', 'check_user_owns_order']

    def get_skip_conditions(self, request):
        return []

    def check_payment_data_is_captured(self, request):
        # if payment data is required for payment method chosen,
        # then preview is only allowed by POSTing payment data.
        if request.method == 'GET' and self.preview and self.payment_method.is_payment_data_required:
            # get order number from preview url.
            view, args, kwargs = resolve(request.path)
            raise checkout_exceptions.FailedPreCondition(
                url=reverse('checkout:payment-details', args=(kwargs['order_number'],)),
                message=_('Enter payment details to preview your order.')
            )

    def check_user_owns_order(self, request):
        if not Order._default_manager.filter(
            Q(user=request.user) |
            Q(guest_email=self.checkout_session.get_guest_email()),
            pk=self.order.pk
        ).exists():
            raise checkout_exceptions.FailedPreCondition(
                url=reverse('customer:order-list'),
                message=_('You cannot make payment for Order #%s.' % self.order.number)
            )

    def check_order_is_approved(self, request, order):
        if order.status != settings.OSCAR_APPROVED_ORDER_STATUS:
            raise checkout_exceptions.FailedPreCondition(
                url=reverse('customer:order-list'),
                message=_(
                    (
                        "Order %s is in %s state. "
                        "Payment can be made only on orders in %s state."
                    ) % (order.number, order.status, settings.OSCAR_APPROVED_ORDER_STATUS)
                )
            )

    def check_order_has_nonzero_total(self, request, order):
        # Check to see if payment is actually required for this order.
        shipping_address = self.get_shipping_address(order)
        shipping_method = self.get_shipping_method(
            order, shipping_address)
        if shipping_method:
            shipping_charge = shipping_method.calculate(order.basket)
        else:
            # It's unusual to get here as a shipping method should be set by
            # the time this skip-condition is called. In the absence of any
            # other evidence, we assume the shipping charge is zero.
            shipping_charge = prices.Price(
                currency=order.basket.currency, excl_tax=D('0.00'),
                tax=D('0.00')
            )
        total = self.get_order_totals(order, shipping_charge)
        if total.excl_tax == D('0.00'):
            # if total price is Zero, then return to order page.
            # with message, that we don't allow orders without a total price.
            raise checkout_exceptions.FailedPreCondition(
                url=reverse('customer:order'),
                message=_(
                    (
                        "Total amount for Order %s is %s. "
                        "Payment can be made only on orders with a valid total amount."
                    ) % (order.number, float(total.excl_tax))
                )
            )

    def skip_unless_payment_data_is_required(self, request, order):
        # Check to see if payment data must be captured for this order.
        # if not required, we render preview page.
        if not self.preview and not self.payment_method.is_payment_data_required:
            raise checkout_exceptions.PassedSkipCondition(
                url=reverse('checkout:preview', args=(order.number,))
            )

    def dispatch(self, request, *args, **kwargs):
        # Assign the checkout session manager so it's available in all checkout
        # views.
        self.checkout_session = CheckoutSessionData(request)

        # assign class attributes.
        self.order = get_object_or_404(Order, number=kwargs['order_number'])
        self.order.basket.strategy = request.strategy
        self.payment_method = self.get_payment_method()
        shipping_address = self.get_shipping_address(self.order)
        self.sales_tax = USSalesTax(self.order.currency, self.order.basket_total_excl_tax, shipping_address)

        # Enforce any pre-conditions for the view.
        try:
            self.check_pre_conditions(request)
        except checkout_exceptions.FailedPreCondition as e:
            for message in e.messages:
                # marking error messages, due to pre condition failure, safe to render HTML.
                messages.error(request, message, extra_tags='safe')
            return http.HttpResponseRedirect(e.url)

        # Check if this view should be skipped
        try:
            self.check_skip_conditions(request)
        except checkout_exceptions.PassedSkipCondition as e:
            return http.HttpResponseRedirect(e.url)

        return super(session.CheckoutSessionMixin, self).dispatch(
            request, *args, **kwargs)

    def get(self, request, order_number, *args, **kwargs):
        try:
            self.check_order_is_approved(request, self.order)
        except checkout_exceptions.FailedPreCondition as e:
            for message in e.messages:
                messages.warning(request, message)
            return http.HttpResponseRedirect(e.url)

        try:
            self.check_order_has_nonzero_total(request, self.order)
        except checkout_exceptions.FailedPreCondition as e:
            logger.error('Order #%s. Order Total is 0. Redirecting to Order page.', self.order.number)
            for message in e.messages:
                messages.warning(request, message)
            return http.HttpResponseRedirect(e.url)

        # skip to preview if payment method does not require payment data.
        try:
            self.skip_unless_payment_data_is_required(request, self.order)
        except checkout_exceptions.PassedSkipCondition as e:
            logger.warning('Order #%s. Skipped payment data capturing as payment method is %s.', self.order.number, self.payment_method.name)
            return http.HttpResponseRedirect(e.url)

        # return to Payment page.
        return super(PaymentDetailsView, self).get(request, order_number, *args, **kwargs)

    def post(self, request, order_number, *args, **kwargs):
        # Posting to payment-details isn't the right thing to do.  Form
        # submissions should use the preview URL.
        if not self.preview:
            return http.HttpResponseBadRequest()

        try:
            self.check_order_is_approved(request, self.order)
        except checkout_exceptions.FailedPreCondition as e:
            for message in e.messages:
                messages.warning(request, message)
            return http.HttpResponseRedirect(e.url)

        try:
            self.check_order_has_nonzero_total(request, self.order)
        except checkout_exceptions.FailedPreCondition as e:
            logger.error('Order #%s. Order Total is 0. Redirecting to Order page.', self.order.number)
            for message in e.messages:
                messages.warning(request, message)
            return http.HttpResponseRedirect(e.url)

        # We use a custom parameter to indicate if this is an attempt to confirm
        # payment (normally from the preview page).  Without this, we assume a
        # payment form is being submitted from the payment details view. In
        # this case, the form needs validating and the order preview shown.
        if request.POST.get('action', '') == 'confirm_payment':
            return self.handle_payment_confirmation(request)
        return self.handle_payment_details_submission(request)

    def handle_payment_details_submission(self, request):
        if self.payment_method.is_payment_data_required:
            if self.payment_method.code == CARD_PAYMENT:
                form = self.form_class(request.POST)
                if form.is_valid():
                    # form is valid, let us show the preview.
                    return self.render_preview(request, form=form)
                # form is invalid, show payment page with error.
                return self.render_payment_details(request, form=form)
        # we dont know to handle the payment method chosen.
        # raise exception stating it.
        logger.error('Order #%s. Capturing payment using method %s is not defined.', self.order.number, self.payment_method.name)
        messages.error(request, _('Capturing payment using method %s is not supported. Please choose another one.' % self.payment_method.name))
        return self.render_payment_details(request)

    def handle_payment_confirmation(self, request):
        """
        Handle a request to confirm payment and redirect to thank you page.
        For some payment method, payment will not be collected,
        for example, Wire Transfer. In that case we just redirect to thank you page.

        This method is normally called after the customer has clicked "confirm"
        on the preview page. It's responsible for (re-)validating any
        form information then building the submission dict to pass to the
        `submit` method.

        If forms are submitted on your payment details view, you should
        override this method to ensure they are valid before extracting their
        data into the submission dict and passing it onto `submit`.
        """
        if self.payment_method.is_payment_data_required:
            if self.payment_method.code == CARD_PAYMENT:
                form = self.form_class(request.POST)
                if form.is_valid():
                    # form is valid, let us charge the card and confirm order.
                    return self.submit(
                        **self.build_submission(
                            basket=self.order.basket,
                            payment_kwargs={
                                'form': form,
                                'method': self.payment_method,
                                'methods': self.get_available_payment_methods()
                            }
                        )
                    )
                else:
                    # form invalid.
                    messages.error(request, 'Unable to process payment now! Please try again.')
                    return self.render_payment_details(request, form=form)
        else:
            if self.payment_method.code == WIRE_TRANSFER:
                logger.warning(
                    (
                        'Order #%s. Payment data is not collected '
                        'as payment method chosen is %s. '
                        'Redirecting to thank you page after alerting admin '
                        'about this and changing order status.'
                    ), self.order.number, self.payment_method.name)
                return self.submit_deferred_payment(
                    **self.build_submission(
                        basket=self.order.basket,
                        payment_kwargs={
                            'method': self.payment_method,
                            'methods': self.get_available_payment_methods()
                        }
                    )
                )
        # we dont know to handle the payment method chosen.
        # raise exception stating it.
        logger.error('Order #%s. Processing payment using method %s is not defined.', self.order.number, self.payment_method.name)
        messages.error(request, _('The payment method %s is not supported. Please choose another one.' % self.payment_method.name))
        return self.render_payment_details(request)

    def build_submission(self, **kwargs):
        """
        Return a dict of data that contains everything required for an order
        submission.  This includes payment details (if any).

        This can be the right place to perform tax lookups and apply them to
        the basket.
        """
        basket = kwargs.get('basket', self.request.basket)
        shipping_address = self.get_shipping_address(self.order)
        shipping_method = self.get_shipping_method(
            self.order, shipping_address)
        billing_address = self.get_billing_address(shipping_address)
        if not shipping_method:
            total = shipping_charge = None
        else:
            shipping_charge = shipping_method.calculate(basket)
            total = self.get_order_totals(
                self.order, shipping_charge=shipping_charge)
        submission = {
            'user': self.request.user,
            'basket': basket,
            'shipping_address': shipping_address,
            'shipping_method': shipping_method,
            'shipping_charge': shipping_charge,
            'billing_address': billing_address,
            'order_total': total,
            'order_kwargs': {},
            'payment_kwargs': {}}

        # If there is a billing address, add it to the payment kwargs as calls
        # to payment gateways generally require the billing address. Note, that
        # it normally makes sense to pass the form instance that captures the
        # billing address information. That way, if payment fails, you can
        # render bound forms in the template to make re-submission easier.
        if billing_address:
            submission['payment_kwargs']['billing_address'] = billing_address

        # Allow overrides to be passed in
        submission.update(kwargs)

        # Set guest email after overrides as we need to update the order_kwargs
        # entry.
        if (not user_is_authenticated(submission['user']) and
                'guest_email' not in submission['order_kwargs']):
            email = self.checkout_session.get_guest_email()
            submission['order_kwargs']['guest_email'] = email

        # apply taxes.
        taxes = self.get_taxes()
        for tax in taxes:
            if getattr(self, 'apply_tax_%s' % tax.code, None):
                # if we need to apply this tax, apply it.
                # if method to apply this tax does not exist,
                # we assume tax is already applied.
                # some taxes like sales tax will be applied while
                # order is first placed, calculated from shipping address.
                getattr(self, 'apply_tax_%s' % tax.code)(submission)

        # set taxes in order so we can display them.
        self.order.computed_taxes = taxes
        return submission

    def submit(self, user, basket, shipping_address, shipping_method,  # noqa (too complex (10))
               shipping_charge, billing_address, order_total,
               payment_kwargs=None, order_kwargs=None):
        """
        Submit a basket for order placement.

        The process runs as follows:

         * Generate an order number
         * Freeze the basket so it cannot be modified any more (important when
           redirecting the user to another site for payment as it prevents the
           basket being manipulated during the payment process).
         * Attempt to take payment for the order
           - If payment is successful, place the order
           - If a redirect is required (eg PayPal, 3DSecure), redirect
           - If payment is unsuccessful, show an appropriate error message

        :basket: The basket to submit.
        :payment_kwargs: Additional kwargs to pass to the handle_payment
                         method. It normally makes sense to pass form
                         instances (rather than model instances) so that the
                         forms can be re-rendered correctly if payment fails.
        :order_kwargs: Additional kwargs to pass to the place_order method
        """
        if payment_kwargs is None:
            payment_kwargs = {}
        if order_kwargs is None:
            order_kwargs = {}

        # Taxes must be known at this point
        assert self.order.is_tax_known, (
            "Basket tax must be set before a user can place an order")
        assert shipping_charge.is_tax_known, (
            "Shipping charge tax must be set before a user can place an order")
        assert self.payment_method.code != WIRE_TRANSFER, (
            "Payment processing using method "
            "%s is not allowed." % self.payment_method.name
        )
        # We also save order number in the session for multi-stage
        # checkouts (eg where we redirect to a 3rd party site and place
        # the order on a different request).
        self.checkout_session.set_order_number(self.order.number)
        logger.info("Order #%s: beginning submission process for basket #%d",
                    self.order.number, basket.id)

        # Also, store a reference to
        # the basket in the session so that we know which basket to thaw if we
        # get an unsuccessful payment response when redirecting to a 3rd party
        # site.
        self.checkout_session.set_submitted_basket(basket)

        # Freeze the order so it cannot be manipulated while the customer is
        # completing payment on a 3rd party site.
        self.freeze_order()

        # We define a general error message for when an unanticipated payment
        # error occurs.
        error_msg = _("A problem occurred while processing payment for this "
                      "order - no payment has been taken.  Please "
                      "contact customer services if this problem persists")

        signals.pre_payment.send_robust(sender=self, view=self)

        try:
            self.handle_payment(self.order.number, order_total, **payment_kwargs)
        except exceptions.RedirectRequired as e:
            # Redirect required (eg PayPal, 3DS)
            logger.info("Order #%s: redirecting to %s", self.order.number, e.url)
            return http.HttpResponseRedirect(e.url)
        except exceptions.UnableToTakePayment as e:
            # Something went wrong with payment but in an anticipated way.  Eg
            # their bankcard has expired, wrong card number - that kind of
            # thing. This type of exception is supposed to set a friendly error
            # message that makes sense to the customer.
            msg = six.text_type(e)
            logger.warning(
                "Order #%s: unable to take payment (%s) - restoring basket",
                self.order.number, msg)
            self.restore_frozen_order()

            # We assume that the details submitted on the payment details view
            # were invalid (eg expired bankcard).
            return self.render_payment_details(
                self.request, error=msg, **payment_kwargs)
        except exceptions.PaymentError as e:
            # A general payment error - Something went wrong which wasn't
            # anticipated.  Eg, the payment gateway is down (it happens), your
            # credentials are wrong - that king of thing.
            # It makes sense to configure the checkout logger to
            # mail admins on an error as this issue warrants some further
            # investigation.
            msg = six.text_type(e)
            logger.error("Order #%s: payment error (%s)", self.order.number, msg,
                         exc_info=True)
            self.restore_frozen_order()
            return self.render_preview(
                self.request, error=error_msg, **payment_kwargs)
        except Exception as e:
            # Unhandled exception - hopefully, you will only ever see this in
            # development...
            logger.error(
                "Order #%s: unhandled exception while taking payment (%s)",
                self.order.number, e, exc_info=True)
            self.restore_frozen_order()
            return self.render_preview(
                self.request, error=error_msg, **payment_kwargs)

        signals.post_payment.send_robust(sender=self, view=self)

        # If all is ok with payment, try and place order
        logger.info("Order #%s: payment successful, placing order",
                    self.order.number)
        try:
            return self.update_order(
                user, basket, shipping_address, shipping_method,
                shipping_charge, billing_address, order_total, **order_kwargs)
        except UnableToPlaceOrder as e:
            # It's possible that something will go wrong while trying to
            # actually place an order.  Not a good situation to be in as a
            # payment transaction may already have taken place, but needs
            # to be handled gracefully.
            msg = six.text_type(e)
            logger.error("Order #%s: unable to place order - %s",
                         self.order.number, msg, exc_info=True)
            self.restore_frozen_order()
            return self.render_preview(
                self.request, error=msg, **payment_kwargs)

    def update_order(self, user, basket, shipping_address,
                     shipping_method, shipping_charge, billing_address,
                     order_total, **order_kwargs):
        # get payment method tax info for whole order.
        payment_method_taxinfo = self.get_payment_method_taxinfo()
        # update order lines first.
        for line in self.order.all_lines():
            # save price information fed in each line.
            # prices calculated incl. tax is fed in each line.
            line.save()
        # update order.
        self.order.basket = basket
        # cellagain custom fields.
        self.order.payment_method = self.payment_method.name
        self.order.payment_method_code = self.payment_method.code
        # update order total.
        self.order.total_incl_tax = order_total.incl_tax
        self.order.total_excl_tax = order_total.excl_tax
        self.order.save()

        # status change.
        OrderEventHandler(user=user).handle_order_status_change(
            self.order,
            settings.OSCAR_PAID_ORDER_STATUS,
            note_msg="Order status changed from '%s' to '%s'." % (self.order.status, settings.OSCAR_PAID_ORDER_STATUS)
        )
        self.save_payment_details(self.order)
        return self.handle_successful_order(self.order)

    def handle_successful_order(self, order):
        response = super(PaymentDetailsView, self).handle_successful_order(order)
        self.request.session['payment_method_code'] = self.payment_method.code
        return response

    def handle_successful_deferred_order(self, order):
        # Send confirmation message (normally an email)
        self.send_deferred_order_admin_alert(order, 'ORDER_PAID_DEFERRED_ADMIN_ALERT')

        # Flush all session data
        self.checkout_session.flush()

        # Save order id in session so thank-you page can load it
        self.request.session['checkout_order_id'] = order.id
        self.request.session['payment_method_code'] = self.payment_method.code

        response = http.HttpResponseRedirect(self.get_success_url())
        self.send_signal(self.request, response, order)
        return response

    def send_deferred_order_admin_alert(self, order, code, **kwargs):
        ctx = self.get_deferred_order_message_context(order)
        try:
            event_type = CommunicationEventType.objects.get(code=code)
        except CommunicationEventType.DoesNotExist:
            # No event-type in database, attempt to find templates for this
            # type and render them immediately to get the messages.  Since we
            # have not CommunicationEventType to link to, we can't create a
            # CommunicationEvent instance.
            messages = CommunicationEventType.objects.get_and_render(code, ctx)
            event_type = None
        else:
            messages = event_type.get_messages(ctx)

        if messages and messages['body']:
            logger.info("Order #%s - sending %s messages to admins.", order.number, code)
            dispatcher = Dispatcher(logger)
            for admin in get_user_model().objects.filter(is_superuser=True):
                dispatcher.dispatch_direct_messages(admin.email, messages)
        else:
            logger.warning("Order #%s - no %s communication event type",
                           order.number, code)

    def get_deferred_order_message_context(self, order):
        ctx = super(PaymentDetailsView, self).get_message_context(order)
        ctx.update({
            'payment_method': self.payment_method,
            'dashboard_order_link': self.request.build_absolute_uri(
                reverse(
                    'dashboard:order-detail',
                    args=(order.number,)
                )
            )
        })
        return ctx

    def submit_deferred_payment(self, user, basket, shipping_address, shipping_method,  # noqa (too complex (10))
               shipping_charge, billing_address, order_total,
               payment_kwargs=None, order_kwargs=None):

        if payment_kwargs is None:
            payment_kwargs = {}
        if order_kwargs is None:
            order_kwargs = {}

        # Taxes must be known at this point
        assert self.order.is_tax_known, (
            "Basket tax must be set before a user can place an order")
        assert shipping_charge.is_tax_known, (
            "Shipping charge tax must be set before a user can place an order")
        assert self.payment_method.code == WIRE_TRANSFER, (
            "Payment processing using methods "
            "%s is only allowed here." % [self.payment_method.name]
        )
        # We also save order number in the session for multi-stage
        # checkouts (eg where we redirect to a 3rd party site and place
        # the order on a different request).
        self.checkout_session.set_order_number(self.order.number)
        logger.info("Order #%s: beginning submission process for basket #%d",
                    self.order.number, basket.id)

        # Also, store a reference to
        # the basket in the session so that we know which basket to thaw if we
        # get an unsuccessful payment response when redirecting to a 3rd party
        # site.
        self.checkout_session.set_submitted_basket(basket)

        OrderEventHandler(user=self.request.user).handle_order_status_change(
            self.order,
            settings.OSCAR_AWAITING_WIRE_TRANSFER_STATUS,
            note_msg="Order status changed from '%s' to '%s'." % (self.order.status, settings.OSCAR_AWAITING_WIRE_TRANSFER_STATUS)
        )
        # cellagain custom fields.
        self.order.payment_method = self.payment_method.name
        self.order.payment_method_code = self.payment_method.code
        self.order.save()

        return self.handle_successful_deferred_order(self.order)

    def freeze_order(self):
        OrderEventHandler(user=self.request.user).handle_order_status_change(
            self.order,
            settings.OSCAR_FREEZE_ORDER_STATUS
        )

    def restore_frozen_order(self):
        OrderEventHandler(user=self.request.user).handle_order_status_change(
            self.order,
            settings.OSCAR_APPROVED_ORDER_STATUS
        )

    def get_payment_method(self):
        code = self.checkout_session.payment_method()
        methods = self.get_available_payment_methods()

        for method in methods:
            if method.code == code:
                return method

    def get_available_payment_methods(self):
        return PaymentRepository().get_payment_methods(
            order=self.order
        )

    def get_shipping_method(self, order, shipping_address=None, **kwargs):
        """
        Return a fixed price shipping method instance from the
        shipping charges stored in the order.

        Shipping address can be used for validation.
        """
        return FixedPriceShipping(order.shipping_excl_tax, order.shipping_incl_tax)

    def get_order_totals(self, order, shipping_charge, **kwargs):
        """
        Returns the total for the order with and without tax
        """
        return OrderTotalCalculator(self.request).calculate(
            order, shipping_charge, **kwargs)

    def get_taxes(self):
        return (self.payment_fee(), self.sales_tax_info())

    def get_payment_method_taxinfo(self):
        return self.payment_method.calculate(self.order)

    def payment_fee(self):
        tax_info = self.get_payment_method_taxinfo()
        if tax_info:
            title = self.payment_method.name
            if self.payment_method.rate:
                title = title + ' (%s%%)' % (self.payment_method.rate * 100).quantize(D('0.01'))
            TaxInfo = namedtuple('TaxInfo', ['title', 'code', 'amount'])
            return TaxInfo(
                title=title,
                code=self.payment_method.code,
                amount=tax_info.tax
            )

    def get_sales_taxinfo(self):
        return self.sales_tax.calculate()

    def sales_tax_info(self):
        tax_info = self.get_sales_taxinfo()
        if tax_info:
            title = self.sales_tax.name
            TaxInfo = namedtuple('TaxInfo', ['title', 'code', 'amount'])
            return TaxInfo(
                title=title,
                code=self.sales_tax.code,
                amount=tax_info.tax
            )

    def apply_tax_payment_fee(self, submission):
        tax_info = self.get_payment_method_taxinfo()
        if tax_info.is_tax_known:
            line_count = len(self.order.all_lines())
            for line in self.order.all_lines():
                # get the tax per line.
                tax_per_line = (tax_info.tax / line_count).quantize(D('0.01'))
                # get tax per product in each line.
                tax_per_product = (tax_per_line / line.quantity).quantize(D('0.01'))
                # we just need to update prices incl. tax.
                line.line_price_incl_tax += tax_per_line
                line.line_price_before_discounts_incl_tax += tax_per_line
                line.unit_price_incl_tax += tax_per_product

            # Recalculate order total to ensure we have a tax-inclusive total
            submission['order_total'] = self.get_order_totals(
                self.order,
                submission['shipping_charge'])

    def apply_tax_wire_transfer(self, submission):
        """
        Method to apply wire transfer fee.
        These tax apply methods have one common pattern,
        apply_tax_<tax code>.
        """
        self.apply_tax_payment_fee(submission)

    def apply_tax_card_payment(self, submission):
        """
        Method to apply card payment fee.
        These tax apply methods have one common pattern,
        apply_tax_<tax code>.
        """
        self.apply_tax_payment_fee(submission)

    def get_shipping_address(self, order):
        """
        Return the shipping address for this order.
        """
        if not order.basket.is_shipping_required():
            return None

        return order.shipping_address

    def get_context_data(self, **kwargs):
        if 'form' not in kwargs and self.payment_method.code == CARD_PAYMENT:
            kwargs['form'] = self.form_class()
        kwargs['order'] = self.order
        kwargs['basket'] = self.order.basket
        kwargs['payment_kwargs'] = {
            'method': self.payment_method,
            'methods': self.get_available_payment_methods()
        }
        kwargs = super(PaymentDetailsView, self).get_context_data(**kwargs)
        return kwargs

    def handle_payment(self, order_number, total, **kwargs):
        """
        This method is responsible for handling payment and recording the
        payment sources (using the add_payment_source method) and payment
        events (using add_payment_event) so they can be
        linked to the order when it is saved later on.
        """
        if total.incl_tax == 0:
            raise exceptions.UnableToTakePayment('Order amount must be non-zero.')
        email = self.request.user if user_is_authenticated(self.request.user) else self.checkout_session.get_guest_email()

        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            # charge the card with order amount and capture immediately.
            stripe_charge_response = stripe.Charge.create(
                amount=int(total.incl_tax) * int(settings.OSCAR_DEFAULT_CURRENCY_LOWEST_VALUE),
                currency=settings.OSCAR_DEFAULT_CURRENCY,
                # payment is captured immediately.
                capture=True,
                description='Payment debited for order %(order_no)s by %(email)s.' % {'email': email, 'order_no': order_number},
                source=kwargs['form'].cleaned_data['payment_method_nonce'],
                statement_descriptor='%(shop_name)s #%(order_no)s.' % {'shop_name': settings.OSCAR_SHOP_NAME, 'order_no': order_number}
            )
        except stripe.error.CardError as e:
            # parse error.
            body = e.json_body
            err = body['error']
            logger.error('Stripe CardError. %s - %s.', err['code'], err['message'])
            # raise Oscar's exception so we can show user friendly messages.
            raise exceptions.UnableToTakePayment(err['message'])
        except (
            stripe.error.RateLimitError,
            stripe.error.AuthenticationError,
            stripe.error.APIConnectionError,
            stripe.error.StripeError
        ) as e:
            logger.error('Stripe gateway error. %s.', e.message)
            raise exceptions.GatewayError(e.message)
        except stripe.error.InvalidRequestError as e:
            logger.error('Stripe invalid gateway request error. %s.', e.message)
            raise exceptions.InvalidGatewayRequestError(e.message)
        else:
            # if there are no exceptions.
            source_type, _ = payment_models.SourceType.objects.get_or_create(name='Stripe')
            source = payment_models.Source(
                source_type=source_type,
                currency=settings.OSCAR_DEFAULT_CURRENCY,
                # instant debit. if deffered debit, we only specify amount_allocated field.
                amount_allocated=total.incl_tax,
                amount_debited=total.incl_tax,
                reference=stripe_charge_response.source.id,
                label='*' * 12 + stripe_charge_response.source.last4
            )
            self.add_payment_source(source)
            # Also record payment event
            self.add_payment_event('Paid', total.incl_tax, reference=stripe_charge_response.id)
        # common 5xx exceptions are gracefully handled by parent PaymentDetailsView.


class ThankYouView(views.ThankYouView):

    def get_object(self):
        order = super(ThankYouView, self).get_object()
        if order:
            # keep payment method object from payment method code in order.
            order.payment_method = self.get_payment_method(order)
        return order

    def get_payment_method(self, order):
        code = order.payment_method_code
        methods = self.get_available_payment_methods(order)

        for method in methods:
            if method.code == code:
                return method

    def get_available_payment_methods(self, order):
        return PaymentRepository().get_payment_methods(
            order=order
        )
