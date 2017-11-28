from django import template

from oscar.core.compat import assignment_tag

register = template.Library()


@assignment_tag(register)
def payment_charge(method, order):
    """
    Template tag for calculating the payment charge for a given payment
    method and order, and injecting it into the template context.
    """
    return method.calculate(order)
