from decimal import Decimal as D
from django.conf import settings
from custom_oscar_apps.payment.methods import CARD_PAYMENT, WIRE_TRANSFER


def stripe_data(request):
    return {
        'stripe_public_key': getattr(settings, 'STRIPE_PUBLIC_KEY', ''),
        'payment_processing_fee_in_percent': (D(getattr(settings, 'PAYMENT_PROCESSING_FEE', '0.00')) * 100).quantize(D('0.1'))
    }


def wiretransfer_data(request):
    return {
        'wiretransfer_details': getattr(settings, 'WIRE_TRANSFER_DETAILS', '')
    }


def oscar_defaults(request):
    return {
        'default_currency': getattr(settings, 'OSCAR_DEFAULT_CURRENCY', 'USD'),
        'min_basket_qty_required': getattr(settings, 'OSCAR_MIN_BASKET_QUANTITY_THRESHOLD_WHOLESALE', 1),
        'show_tax_separately': True,
        'initial_order_status': getattr(settings, 'OSCAR_INITIAL_ORDER_STATUS', ''),
        'approved_order_status': getattr(settings, 'OSCAR_APPROVED_ORDER_STATUS', ''),
        'frozen_order_status': getattr(settings, 'OSCAR_FREEZE_ORDER_STATUS', ''),
    }


def misc_settings_data(request):
    return {
        'livechat_id': getattr(settings, 'LIVECHAT_ID', None),
        'company_billing_address': getattr(settings, 'COMPANY_BILLING_ADDRESS', None),
        'card_payment_code': CARD_PAYMENT,
        'wire_transfer_code': WIRE_TRANSFER,
        'lockdown_message_header': getattr(settings, 'LOCKDOWN_MESSAGE_HEADER', None),
        'lockdown_message': getattr(settings, 'LOCKDOWN_MESSAGE', None),
    }
