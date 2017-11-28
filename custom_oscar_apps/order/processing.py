import logging
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.urlresolvers import NoReverseMatch, reverse
from oscar.apps.order import processing
from oscar.apps.order import exceptions as order_exceptions
from oscar.core.loading import get_class, get_model

logger = logging.getLogger('oscar.checkout')
Dispatcher = get_class('customer.utils', 'Dispatcher')
CommunicationEventType = get_model('customer', 'CommunicationEventType')


class EventHandler(processing.EventHandler):
    """
    Handle requested order events.

    This is an important class: it houses the core logic of your shop's order
    processing pipeline.
    """
    # Default code for the email to send after successful status change.
    communication_type_code = 'ORDER_APPROVED'

    def __init__(self, user=None):
        super(EventHandler, self).__init__(user)

    def handle_order_status_change(self, order, new_status, note_msg=None):
        """
        Handle a requested order status change

        This method is not normally called directly by client code.  The main
        use-case is when an order is cancelled, which in some ways could be
        viewed as a shipping event affecting all lines.
        """
        old_status = order.status
        try:
            order.set_status(new_status)
            if self.user.is_superuser:
                # if admin is liu.
                if old_status == settings.OSCAR_INITIAL_ORDER_STATUS and new_status == settings.OSCAR_APPROVED_ORDER_STATUS:
                    # if old status was awaiting approval and new status is approved.
                    self.send_order_approved_message(order, self.communication_type_code)
        except order_exceptions.InvalidOrderStatus as e:
            raise e
        if note_msg:
            self.create_note(order, note_msg)

    def send_order_approved_message(self, order, code, **kwargs):
        ctx = self.get_message_context(order)
        try:
            event_type = CommunicationEventType.objects.get(code=code)
        except CommunicationEventType.DoesNotExist:
            # No event-type in database, attempt to find templates for this
            # type and render them immediately to get the messages.  Since we
            # have not CommunicationEventType to link to, we can't create a
            # CommunicationEvent instance.
            messages = CommunicationEventType.objects.get_and_render(code, ctx)
            event_type = None
        else:
            messages = event_type.get_messages(ctx)

        if messages and messages['body']:
            logger.info("Order #%s - sending %s messages", order.number, code)
            dispatcher = Dispatcher(logger)
            dispatcher.dispatch_order_messages(
                order,
                messages,
                event_type,
                **kwargs
            )
        else:
            logger.warning("Order #%s - no %s communication event type",
                           order.number, code)

    def get_message_context(self, order):
        site = Site.objects.get_current()
        try:
            order_payment_link = 'http://%s%s' % (site.domain, reverse('checkout:payment-method', args=(order.number,)))
        except NoReverseMatch:
            # We don't care that much if we can't resolve the URL.
            order_payment_link = None
            pass
        ctx = {
            'user': self.user,
            'order': order,
            'order_payment_link': order_payment_link,
            'lines': order.lines.all(),
            'site': site
        }
        return ctx
