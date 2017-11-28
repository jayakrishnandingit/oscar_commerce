from collections import namedtuple
from decimal import Decimal as D
from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from oscar.apps.order.abstract_models import AbstractOrder, AbstractLine
from oscar.core.loading import get_class

TaxInfo = namedtuple('TaxInfo', ['title', 'amount'])
PaymentRepository = get_class('payment.repository', 'Repository')
USSalesTax = get_class('partner.strategy', 'USStateWiseSalesTax')


class Order(AbstractOrder):
    payment_method = models.CharField(
        _("Payment method"), max_length=128, blank=True, default="")

    # Identifies payment method code.
    payment_method_code = models.CharField(blank=True, max_length=128, default="")

    def __init__(self, *args, **kwargs):
        super(Order, self).__init__(*args, **kwargs)

        # We keep a cached copy of the order lines as we refer to them often
        # within the same request cycle.  Also, applying taxes for preview
        # during payment cycle is less expensive this way.
        self._lines = None

    def all_lines(self):
        """
        Return a cached set of order lines.

        This is important for offers as they alter the line models and you
        don't want to reload them from the DB as that information would be
        lost.
        """
        if self.id is None:
            return self.lines.none()
        if self._lines is None:
            self._lines = (
                self.lines
                .select_related('product', 'stockrecord')
                .prefetch_related(
                    'attributes', 'product__images')
                .order_by(self._meta.pk.name))
        return self._lines

    @property
    def is_tax_known(self):
        return all([line.is_tax_known for line in self.all_lines()])

    @property
    def discount_tax(self):
        return self.total_discount_incl_tax - self.total_discount_excl_tax

    @property
    def discount_tax_info(self):
        return TaxInfo(
            title='Tax on discount',
            amount=self.discount_tax
        )

    @property
    def shipping_tax_info(self):
        return TaxInfo(
            title='Shipping tax',
            amount=self.shipping_tax
        )


    @property
    def taxes(self):
        return (
            self.payment_fee,
            self.sales_tax_info,
            self.shipping_tax_info,
            self.discount_tax_info
        )

    @property
    def sales_tax_info(self):
        tax_info = self.get_sales_taxinfo()
        if tax_info:
            return TaxInfo(
                title=self.sales_tax_obj.name,
                amount=tax_info.tax
            )

    @property
    def payment_fee(self):
        tax_info = self.get_payment_method_taxinfo()
        if tax_info:
            title = self._payment_method.name
            if self._payment_method.rate:
                title = title + ' (%s%%)' % (self._payment_method.rate * 100).quantize(D('0.01'))
            return TaxInfo(
                title=title,
                amount=tax_info.tax
            )

    @property
    def _payment_method(self):
        for method in PaymentRepository().get_payment_methods(order=self):
            if method.code == self.payment_method_code:
                return method

    @property
    def payment_method_info(self):
        return self._payment_method

    @property
    def sales_tax_obj(self):
        return USSalesTax(
            self.currency,
            self.basket_total_excl_tax,
            self.shipping_address
        )

    @property
    def billed_from(self):
        return getattr(settings, 'COMPANY_BILLING_ADDRESS', None)

    def get_payment_method_taxinfo(self):
        return self._payment_method.calculate(self)

    def get_sales_taxinfo(self):
        return self.sales_tax_obj.calculate()


class Line(AbstractLine):

    @property
    def is_tax_known(self):
        if self.line_price_incl_tax is None:
            return False
        return True

from oscar.apps.order.models import *  # noqa
