from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext_lazy as _

from custom_oscar_apps.payment import methods as payment_methods


class Repository(object):
    """
    Repository class responsible for returning PaymentMethod
    objects for a given user, basket etc
    """

    # We default to Card and Wire transfer methods. This should be a list of
    # instantiated payment methods.
    methods = (payment_methods.WireTransfer(),)

    # API

    def get_payment_methods(self, order, **kwargs):
        """
        Return a list of all applicable payment method instances for a given
        order, etc.
        """

        methods = self.get_available_payment_methods(
            order=order, **kwargs)
        return methods

    def get_default_payment_method(self, order, **kwargs):
        """
        Return a 'default' payment method to show on the order page to give
        the customer an indication of what their order will cost.
        """
        payment_methods = self.get_payment_methods(
            order, **kwargs)
        if len(payment_methods) == 0:
            raise ImproperlyConfigured(
                _("You need to define some payment methods"))

        # Assume first returned method is default.
        return payment_methods[0]

    # Helpers

    def get_available_payment_methods(self, order, **kwargs):
        """
        Return a list of all applicable shipping method instances for a given
        order, address etc. This method is intended to be overridden.
        """
        return self.methods
