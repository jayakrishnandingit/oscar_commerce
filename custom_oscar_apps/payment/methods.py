from decimal import Decimal as D
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from oscar.core import prices


class Base(object):
    code = ''
    name = ''

    rate = None

    @property
    def is_payment_data_required(self):
        raise NotImplementedError

    def calculate(self, order):
        raise NotImplementedError


class Card(Base):
    code = 'card_payment'
    name = _('Credit/Debit Card Payment')
    description = _((
        'Select this method to fill in details of your card'
        '&nbsp;from which you want us to debit the order amount.'
        '<br />'
        'The order will be instantly marked as paid and allows'
        '&nbsp;us to process the order immediately.'
        '<br /> The information we collect here is absolutely safe'
        '&nbsp;and is transferred using secure connection.'
        '<br />'
        '<b>This will incur a %s%% additional fee.</b>'
    ) % (D(settings.PAYMENT_PROCESSING_FEE) * 100).quantize(D('0.01')))

    rate = D(settings.PAYMENT_PROCESSING_FEE)  # 0.035

    @property
    def is_payment_data_required(self):
        return True

    def calculate(self, order):
        return prices.Price(
            currency=order.currency,
            excl_tax=D('0.00'),
            # we insist a tax percentage on order total.
            tax=(order.total_excl_tax * self.rate).quantize(D('0.01'))
        )

CARD_PAYMENT = Card().code


class WireTransfer(Base):
    code = 'wire_transfer'
    name = _('Wire Transfer')
    description = _((
        'Here we allow for a deferred payment.'
        '&nbsp;You can pay to us using Wire Transfer from your bank.'
        '&nbsp;We will display our account details for you to do Wire Transfer.'
        '&nbspOnce the amount is credited in our account we start'
        '&nbsp;dispatch of your order.'
        '<br />'
        '<b>Here the order processing will incur some delay.</b>'
    ))

    rate = D('0.00')

    @property
    def is_payment_data_required(self):
        return False

    def calculate(self, order):
        return prices.Price(
            currency=order.currency,
            excl_tax=D('0.00'),
            tax=D('0.00')
        )

WIRE_TRANSFER = WireTransfer().code
