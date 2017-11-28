from django.conf.urls import url
from oscar.apps.checkout.app import CheckoutApplication as CoreCheckoutApplication
from oscar.core.loading import get_class


class CheckoutApplication(CoreCheckoutApplication):
    name = 'checkout'

    post_paid_order_view = get_class('checkout.views', 'PlacePostPaidOrderView')
    thank_you_post_paid_order_view = get_class('checkout.views', 'PostPaidOrderThankYouView')
    payment_method_view = get_class('checkout.views', 'PaymentMethodView')
    payment_details_view = get_class('checkout.views', 'PaymentDetailsView')

    def get_urls(self):
        urls = super(CheckoutApplication, self).get_urls()
        urls += [
            url(
                r'place-post-paid-order/$',
                self.post_paid_order_view.as_view(),
                name='post-paid-order'
            ),
            url(
                r'thank-you-post-paid-order/$',
                self.thank_you_post_paid_order_view.as_view(),
                name='thank-you-post-paid-order'
            ),

            # Payment views
            url(r'payment-method/(?P<order_number>[-\w]+)/$',
                self.payment_method_view.as_view(), name='payment-method'),
            url(r'payment-details/(?P<order_number>[-\w]+)/$',
                self.payment_details_view.as_view(), name='payment-details'),
            # Preview and thankyou
            url(r'preview/(?P<order_number>[-\w]+)/$',
                self.payment_details_view.as_view(preview=True),
                name='preview'),
        ]
        return self.post_process_urls(urls)

    def get_url_decorator(self, pattern):
        return super(CheckoutApplication, self).get_url_decorator(pattern)


application = CheckoutApplication()
