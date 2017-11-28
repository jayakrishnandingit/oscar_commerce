from decimal import Decimal as D
from oscar.core import prices
from oscar.apps.checkout.calculators import *


class EschewBasketOrderTotalCalculator(object):
    """
    Calculator class for calculating the order total, independent of basket.
    """

    def __init__(self, request=None):
        # We store a reference to the request as the total may
        # depend on the user or the other checkout data in the session.
        # Further, it is very likely that it will as shipping method
        # always changes the order total.
        self.request = request

    def calculate(self, order, shipping_charge, **kwargs):
        updated_lines = kwargs.get('updated_lines', [])

        # query using special method in model.
        # this allows caching of the lines.
        # hence any additional info like taxes added to
        # line prices are available here for total calculation.
        query = order.all_lines()
        updated_total_excl_tax = D('0.00')
        updated_total_incl_tax = D('0.00')
        if len(updated_lines) > 0:
            # exclude the updated lines from query.
            query = query.exclude(id__in=map(lambda ul: ul.id, updated_lines))
            updated_total_excl_tax = sum([each_line.line_price_excl_tax for each_line in updated_lines])
            updated_total_incl_tax = sum([each_line.line_price_incl_tax for each_line in updated_lines])

        total_excl_tax = (
            sum([line.line_price_excl_tax for line in query]) +
            updated_total_excl_tax
        )
        total_incl_tax = (
            sum([line.line_price_incl_tax for line in query]) +
            updated_total_incl_tax
        )

        # add shipping charge.
        total_excl_tax += shipping_charge.excl_tax
        total_incl_tax += shipping_charge.incl_tax
        return prices.Price(
            currency=order.basket.currency,
            excl_tax=total_excl_tax, incl_tax=total_incl_tax)
