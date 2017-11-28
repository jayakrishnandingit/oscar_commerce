from decimal import Decimal as D
from django import http
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView
from django.template.loader import get_template
from django.contrib import messages
from django.conf import settings
from weasyprint import HTML, CSS
from oscar.apps.dashboard.orders import views
from oscar.core.loading import get_class, get_model

Order = get_model('order', 'Order')
OrderTotalCalculator = get_class('checkout.calculators', 'EschewBasketOrderTotalCalculator')
OrderEventHandler = get_class('order.processing', 'EventHandler')
ShippingRepository = get_class('shipping.repository', 'Repository')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
FixedPriceShipping = get_class('shipping.methods', 'FixedPrice')


class OrderDetailView(views.OrderDetailView):
    """
    Overriding Dashboard view to display a single order.

    Supports the permission-based dashboard.
    """

    # These strings are method names that are allowed to be called from a
    # submitted form.
    order_actions = ('save_note', 'delete_note', 'change_order_status',
                     'create_order_payment_event', 'update_order_shipping_charge')
    line_actions = ('change_line_statuses', 'create_shipping_event',
                    'create_payment_event', 'delete_lines',
                    'update_lines_quantity', 'update_line_unit_price')

    def _basket_lines_cache_bust(self, basket):
        basket._lines = None

    def _get_line_tax(self, order_line):
        # tax incl. and excl. prices on the line and
        # dividing by the quantity in the line.
        return order_line.line_price_incl_tax - order_line.line_price_excl_tax

    def _get_unit_tax(self, order_line):
        line_tax = self._get_line_tax(order_line)
        return (line_tax / order_line.quantity).quantize(D('0.01'))

    def _restore_basket(self, basket):
        basket.status = basket.OPEN
        basket.save()

    def _submit_basket(self, basket):
        basket.status = basket.SUBMITTED
        basket.save()

    def _create_order_note(self, order, user, msg):
        OrderEventHandler(user).create_note(
            order=order,
            message=msg,
            note_type='Admin'
        )

    def _update_order_total(self, request, order, shipping_charge, updated_lines=[], deleted_lines=[]):
        order_total = OrderTotalCalculator(request).calculate(
            order, shipping_charge,
            updated_lines=updated_lines,
            deleted_lines=deleted_lines
        )
        order.total_incl_tax = order_total.incl_tax
        order.total_excl_tax = order_total.excl_tax
        order.save()

    def update_line_unit_price(self, request, order, lines, quantities):
        basket = order.basket
        # make basket editable.
        self._restore_basket(basket)
        basket.strategy = request.strategy

        updated_lines = []
        for line in lines:
            unit_price_excl_tax = request.POST.get('selected_line_unit_price_excl_tax_%s' % line.id)
            try:
                unit_price_excl_tax = D(unit_price_excl_tax)
            except InvalidOperation:
                unit_price_excl_tax = None
            if unit_price_excl_tax is None or unit_price_excl_tax <= 0:
                error_msg = _("The entered price for line #%s is not valid.")
                return self.reload_page(error=error_msg % line.id)

            if line.unit_price_excl_tax != unit_price_excl_tax:
                # extra validation. we only allow update
                # if price input has changed.
                for basket_line in basket.all_lines():
                    if basket_line.line_reference == basket._create_line_reference(
                            line.product, line.stockrecord, None):
                        # update unit price columns in a order line.
                        old_price = (float(line.unit_price_excl_tax), float(line.unit_price_incl_tax))
                        line.unit_price_excl_tax = unit_price_excl_tax
                        line.unit_price_incl_tax = unit_price_excl_tax + self._get_unit_tax(line)
                        new_price = (float(line.unit_price_excl_tax), float(line.unit_price_incl_tax))
                        # retrive discounts if any, so we can update them later after price change.
                        line_discount_excl_tax = line.discount_excl_tax
                        line_discount_incl_tax = line.discount_incl_tax
                        # make price changes according to new unit price.
                        line.line_price_before_discounts_excl_tax = line.quantity * line.unit_price_excl_tax
                        line.line_price_before_discounts_incl_tax = line.quantity * line.unit_price_incl_tax
                        # apply discounts and update discounted price columns.
                        line.line_price_excl_tax = line.line_price_before_discounts_excl_tax - line_discount_excl_tax
                        line.line_price_incl_tax = line.line_price_before_discounts_incl_tax - line_discount_incl_tax
                        # save to database.
                        line.save()
                        # update LinePrice entry.
                        # only one entry per Line must be here in our case.
                        line_prices = line.prices.first()
                        line_prices.price_excl_tax = unit_price_excl_tax
                        line_prices.price_incl_tax = unit_price_excl_tax + self._get_unit_tax(line)
                        line_prices.save()
                        order_note = (
                            'Line #%s unit price '
                            'changed from %s to %s.'
                        ) % (line.id, old_price, new_price)
                        self._create_order_note(order, request.user, order_note)
                        # append affected lines for reporting.
                        updated_lines.append(line)
        # submit basket.
        self._submit_basket(basket)
        order.basket = basket
        # create a fixed price shipping method from shipping charges in order
        # for order total calculation.
        shipping_method = FixedPriceShipping(order.shipping_excl_tax, order.shipping_incl_tax)
        # update order total.
        self._update_order_total(
            request, order, shipping_method.calculate(order.basket),
            updated_lines=updated_lines
        )
        messages.info(request, _("Updated unit price for lines %s." % map(lambda l: l.id, updated_lines)))
        return self.reload_page()

    def delete_lines(self, request, order, lines, quantities):
        if order.lines.all().count() == len(lines):
            return self.reload_page(
                error=_("Cannot delete all line items.")
            )
        if order.lines.filter(id__in=map(lambda l: l.id, lines), status__in=settings.OSCAR_CANNOT_DELETE_LINE_STATUSES).count() > 0:
            return self.reload_page(
                error=_((
                    "Some lines cannot be deleted "
                    "as they are in %s status."
                ) % settings.OSCAR_CANNOT_DELETE_LINE_STATUSES)
            )

        # delete the basket lines and lines.
        order.basket.strategy = request.strategy
        for line in lines:
            try:
                basket_line = order.basket.all_lines().get(
                    line_reference=order.basket._create_line_reference(
                        line.product, line.stockrecord, None)
                )
            except ObjectDoesNotExist as e:
                messages.warning(request, _("Basket line matching line id %s not found." % line.id))
                continue
            else:
                basket_line.delete()
                order_note = 'Line #%s deleted.' % line.id
                self._create_order_note(order, request.user, order_note)
                line.delete()  # all related tables must be deleted since on_delete is CASCADE.

        # create a fixed price shipping method from shipping charges in order
        # for order total calculation.
        shipping_method = FixedPriceShipping(order.shipping_excl_tax, order.shipping_incl_tax)
        # calculate order total again.
        self._update_order_total(
            request, order, shipping_method.calculate(order.basket)
        )
        messages.info(request, 'Deleted selected lines from order. Recalculated order total.')
        return self.reload_page()

    def update_lines_quantity(self, request, order, lines, quantities):
        basket = order.basket
        # make basket editable.
        self._restore_basket(basket)
        basket.strategy = request.strategy

        updated_lines = []
        lines_to_update_stockrecord = []
        quantities_to_update_stockrecord = []
        for line, quantity in zip(lines, quantities):
            if line.quantity != quantity:
                # extra validation. we only allow update
                # if quantity input has changed.
                # other quantity validations are done in super class.
                for basket_line in basket.all_lines():
                    if basket_line.line_reference == basket._create_line_reference(
                            line.product, line.stockrecord, None):
                        # update basket line quantity.
                        basket_line.quantity = quantity
                        # update line quantity and line prices.
                        line.quantity = quantity
                        # retrive discounts if any, so we can update them later after price change.
                        line_discount_excl_tax = line.discount_excl_tax
                        line_discount_incl_tax = line.discount_incl_tax
                        # make price changes according to new quantity.
                        line.line_price_before_discounts_excl_tax = line.quantity * line.unit_price_excl_tax
                        line.line_price_before_discounts_incl_tax = line.quantity * line.unit_price_incl_tax
                        # apply discounts and update discounted price columns.
                        line.line_price_excl_tax = line.line_price_before_discounts_excl_tax - line_discount_excl_tax
                        line.line_price_incl_tax = line.line_price_before_discounts_incl_tax - line_discount_incl_tax
                        # save to database.
                        line.save()
                        basket_line.save()
                        # update LinePrice entry.
                        # only one entry per Line must be here in our case.
                        line_prices = line.prices.first()
                        line_prices.quantity = quantity
                        line_prices.save()
                        if line.product.product_class.track_stock:
                            # save these lines to update stockrecord.
                            lines_to_update_stockrecord.append(line)
                            quantities_to_update_stockrecord.append(line.quantity - quantity)
                        order_note = 'Line #%s quantity changed to %s.' % (line.id, line.quantity)
                        self._create_order_note(order, request.user, order_note)
                        # append affected lines for reporting.
                        updated_lines.append(line)
        # update stockrecord for stock tracking required products.
        OrderEventHandler(request.user).cancel_stock_allocations(
            order, lines_to_update_stockrecord, quantities_to_update_stockrecord
        )
        # submit basket.
        self._submit_basket(basket)
        order.basket = basket
        # create a fixed price shipping method from shipping charges in order
        # for order total calculation.
        shipping_method = FixedPriceShipping(order.shipping_excl_tax, order.shipping_incl_tax)
        # update order total.
        self._update_order_total(
            request, order, shipping_method.calculate(order.basket),
            updated_lines=updated_lines
        )
        messages.info(request, _("Updated quantity for lines %s." % map(lambda l: l.id, updated_lines)))
        return self.reload_page()

    def update_order_shipping_charge(self, request, order):
        excl_tax = request.POST.get('shipping_excl_tax') or None
        incl_tax = request.POST.get('shipping_incl_tax') or None

        if excl_tax is None or incl_tax is None:
            return self.reload_page(error=_("Excl. Tax and Incl. Tax cannot be empty."))

        try:
            excl_tax = D(excl_tax)
        except InvalidOperation:
            return self.reload_page(error=_("Please choose a valid excl. tax."))

        try:
            incl_tax = D(incl_tax)
        except InvalidOperation:
            return self.reload_page(error=_("Please choose a valid incl. tax."))

        if excl_tax > incl_tax:
            return self.reload_page(error=_("Incl tax must be greater than or equal to excl tax."))

        # set strategy so that price calculations can be performed.
        order.basket.strategy = request.strategy

        # create a fixed price shipping method for order total calculation.
        shipping_method = FixedPriceShipping(excl_tax, incl_tax)
        shipping_charge = shipping_method.calculate(order.basket)
        # for reporting.
        old_tax = (float(order.shipping_excl_tax), float(order.shipping_incl_tax))
        new_tax = (float(excl_tax), float(incl_tax))
        # set new charges.
        order.shipping_excl_tax = shipping_charge.excl_tax
        order.shipping_incl_tax = shipping_charge.incl_tax
        # update order total and save order.
        self._update_order_total(request, order, shipping_charge)
        order_note = 'Shipping charge updated from %s to %s.' % (old_tax, new_tax)
        self._create_order_note(order, request.user, order_note)
        messages.info(request, _("Updated shipping charge."))
        return self.reload_page()


class OrderInvoiceView(DetailView):
    model = Order
    context_object_name = 'order'
    template_name = 'dashboard/orders/invoice_pdf_template.html'
    http_method_names = ['post']

    # These strings are method names that are allowed to be called from a
    # submitted form.
    order_actions = ('download_pdf',)
    line_actions = ()

    def get_object(self, queryset=None):
        return views.get_order_for_user_or_404(
            self.request.user, self.kwargs['number'])

    def post(self, request, *args, **kwargs):
        # For POST requests, we use a dynamic dispatch technique where a
        # parameter specifies what we're trying to do with the form submission.
        # We distinguish between order-level actions and line-level actions.

        order = self.object = self.get_object()

        # Look for order-level action first
        if 'order_action' in request.POST:
            return self.handle_order_action(
                request, order, request.POST['order_action'])

        # Look for line-level action
        if 'line_action' in request.POST:
            return self.handle_line_action(
                request, order, request.POST['line_action'])

        return self.reload_page(error=_("No valid action submitted"))

    def handle_order_action(self, request, order, action):
        if action not in self.order_actions:
            return self.reload_page(error=_("Invalid action"))
        return getattr(self, action)(request, order)

    def handle_line_action(self, request, order, action):
        if action not in self.line_actions:
            return self.reload_page(error=_("Invalid action"))

        raise NotImplementedError

    def download_pdf(self, request, order):
        # filename must be email attachment compatible.
        filename = 'Order_{number}_Invoice'.format(
            number=order.number
        )
        base_url = request.build_absolute_uri('/')
        pdf = HTML(
            string=get_template(
                self.template_name
            ).render(self.get_context_data()),
            base_url=base_url
        ).write_pdf()
        response = http.HttpResponse(pdf)
        response['Content-Type'] = 'application/pdf'
        response['Content-Disposition'] = 'attachment; filename="{}.pdf"'.format(filename)
        return response
