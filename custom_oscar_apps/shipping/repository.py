from decimal import Decimal as D
from django.conf import settings
from oscar.apps.shipping import repository
from oscar.apps.shipping import methods as shipping_methods


class Repository(repository.Repository):
    # We default to just fixed price shipping.
    methods = [
        shipping_methods.FixedPrice(
            D(settings.OSCAR_FIXED_PRICE_SHIPPING_CHG_EXCL_TAX),
            D(settings.OSCAR_FIXED_PRICE_SHIPPING_CHG_INCL_TAX)
        )
    ]
