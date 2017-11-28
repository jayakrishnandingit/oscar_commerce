from oscar.apps.partner import availability


class Available(availability.Available):
    # we do not want to show a "Available" message to customers.
    message = ""
