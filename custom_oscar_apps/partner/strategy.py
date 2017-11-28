from decimal import Decimal as D
from django.conf import settings
from oscar.core import prices
from oscar.apps.partner import strategy


class Selector(object):
    """
    Responsible for returning the appropriate strategy class for a given
    user/session.

    This can be called in three ways:

    #) Passing a request and user.  This is for determining
       prices/availability for a normal user browsing the site.

    #) Passing just the user.  This is for offline processes that don't
       have a request instance but do know which user to determine prices for.

    #) Passing nothing.  This is for offline processes that don't
       correspond to a specific user.  Eg, determining a price to store in
       a search index.

    """

    def strategy(self, request=None, user=None, **kwargs):
        """
        Return an instanticated strategy instance
        """
        # Default to the backwards-compatible strategy of picking the first
        # stockrecord but charging zero tax.
        return CellAgain(request)


class CellAgain(strategy.UseFirstStockRecord, strategy.StockRequired, strategy.DeferredTax, strategy.Structured):
    """
    Strategy for adding any extra processing fee that:

    - uses the first stockrecord for each product (effectively assuming
      there is only one).
    - requires that a product has stock available to be bought
    - doesn't apply a tax to product prices (normally this will be done
      after the shipping address/payment details is entered).
    """


class BaseSalesTax(object):
    code = ''
    name = ''

    rate = None

    @property
    def is_tax_known(self):
        return self.rate is not None

    def calculate(self):
        raise NotImplementedError


class USStateWiseSalesTax(BaseSalesTax):
    code = 'us_state_sales_tax'

    def __init__(self, currency, excl_tax, shipping_address):
        self.currency = currency
        self.excl_tax = excl_tax
        self.shipping_address = shipping_address

    @property
    def name(self):
        return '%s state sales tax (%s%%)' % (
            self.shipping_address.state,
            (self.rate * 100).quantize(D('0.01'))
        )

    @property
    def description(self):
        return 'Sales tax of %s is applicable for the state of %s.' % (
            (self.rate * 100).quantize(D('0.01')),
            self.shipping_address.state
        )

    @property
    def rate(self):
        if self.shipping_address:
            return D(settings.US_STATE_WISE_SALES_TAX.get(self.shipping_address.state.lower(), '0.00'))
        return D('0.00')

    def calculate(self):
        return prices.Price(
            currency=self.currency,
            excl_tax=self.excl_tax,
            tax=(self.excl_tax * self.rate).quantize(D('0.01'))
        )
