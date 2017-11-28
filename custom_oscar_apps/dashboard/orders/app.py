from django.conf.urls import url
from oscar.core.loading import get_class
from oscar.apps.dashboard.orders import app


class OrdersDashboardApplication(app.OrdersDashboardApplication):
    permissions_map = {
        'order-list': (['is_staff'], ['partner.dashboard_access']),
        'order-stats': (['is_staff'], ['partner.dashboard_access']),
        'order-detail': (['is_staff'], ['partner.dashboard_access']),
        'order-detail-note': (['is_staff'], ['partner.dashboard_access']),
        'order-line-detail': (['is_staff'], ['partner.dashboard_access']),
        'order-shipping-address': (['is_staff'], ['partner.dashboard_access']),
        'order-invoice-download': (['is_staff'], ['partner.dashboard_access']),
    }

    order_invoice_download_view = get_class('dashboard.orders.views', 'OrderInvoiceView')

    def get_urls(self):
        urls = super(OrdersDashboardApplication, self).get_urls()

        urls += [
            url(r'^(?P<number>[-\w]+)/download-invoice/$',
                self.order_invoice_download_view.as_view(), name='order-invoice-download'),
        ]
        return self.post_process_urls(urls)

application = OrdersDashboardApplication()
