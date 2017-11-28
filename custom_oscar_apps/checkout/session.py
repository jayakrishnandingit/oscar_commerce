from django import http
from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse, resolve
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _, ungettext_lazy
from oscar.apps.checkout import session, exceptions
from oscar.core.loading import get_class

CheckoutSessionData = get_class(
    'checkout.utils', 'CheckoutSessionData')


class CheckoutSessionMixin(session.CheckoutSessionMixin):

    def dispatch(self, request, *args, **kwargs):
        # Assign the checkout session manager so it's available in all checkout
        # views.
        self.checkout_session = CheckoutSessionData(request)

        # Enforce any pre-conditions for the view.
        try:
            self.check_pre_conditions(request)
        except exceptions.FailedPreCondition as e:
            for message in e.messages:
                # marking error messages, due to pre condition failure, safe to render HTML.
                messages.error(request, message, extra_tags='safe')
            return http.HttpResponseRedirect(e.url)

        # Check if this view should be skipped
        try:
            self.check_skip_conditions(request)
        except exceptions.PassedSkipCondition as e:
            return http.HttpResponseRedirect(e.url)

        return super(session.CheckoutSessionMixin, self).dispatch(
            request, *args, **kwargs)

    def get_pre_conditions(self, request):
        """
        Return the pre-condition method names to run for this view
        """
        if self.pre_conditions is None:
            return []
        return self.pre_conditions + ['check_basket_has_required_quantity']

    def check_basket_has_required_quantity(self, request):
        if request.basket.num_items < settings.OSCAR_MIN_BASKET_QUANTITY_THRESHOLD_WHOLESALE:
            items_required = settings.OSCAR_MIN_BASKET_QUANTITY_THRESHOLD_WHOLESALE - request.basket.num_items
            msg = mark_safe("<b>You need to add %s more item to your basket to checkout.</b>" % items_required)
            msg_plural = mark_safe("<b>You need to add %s more items to your basket to checkout.</b>" % items_required)
            raise exceptions.FailedPreCondition(
                url=reverse('basket:summary'),
                message=ungettext_lazy(
                    msg,
                    msg_plural,
                    items_required
                )
            )
