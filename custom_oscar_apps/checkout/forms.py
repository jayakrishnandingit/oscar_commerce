import logging
import stripe
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django import forms

logger = logging.getLogger('stripe')


class PaymentMethodForm(forms.Form):
    method_code = forms.ChoiceField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        methods = kwargs.pop('methods', [])
        super(PaymentMethodForm, self).__init__(*args, **kwargs)
        self.fields['method_code'].choices = ((m.code, m.name) for m in methods)


class StripePaymentForm(forms.Form):
    # stripe card object funding types.
    CREDIT_CARD = 'credit'
    DEBIT_CARD = 'debit'
    UNKNOWN = 'unknown'
    PREPAID_CARD = 'prepaid'

    def __init__(self, *args, **kwargs):
        super(StripePaymentForm, self).__init__(*args, **kwargs)

    payment_method_nonce = forms.CharField(required=True, widget=forms.HiddenInput)
    stripe_token_data = None

    def clean(self):
        cleaned_data = super(StripePaymentForm, self).clean()
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            # retrieve the payment details from the stripe token.
            # this helps in showing payment information in preview.
            self.stripe_token_data = stripe.Token.retrieve(cleaned_data.get('payment_method_nonce'))
            # add the obfuscated card number. a bad side of stripe.
            self.stripe_token_data.card.obfuscated_number = '*' * 12 + self.stripe_token_data.card.last4
        except (
            stripe.error.AuthenticationError,
            stripe.error.APIConnectionError,
            stripe.error.InvalidRequestError,
            stripe.error.RateLimitError,
            stripe.error.StripeError
        ) as e:
            logger.error('Stripe gateway error while retrieving token data %s. %s.', cleaned_data.get('payment_method_nonce'), e.message)
            raise forms.ValidationError(_('We are unable to process payment right now. Please try after sometime.'))
        except stripe.error.CardError as e:
            # parse error.
            body = e.json_body
            err = body['error']
            logger.error('Stripe CardError. %s - %s.', err['code'], err['message'])
            raise forms.ValidationError(err['message'])
