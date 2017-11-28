# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def forwards_func(apps, schema_editor):
    # We get the model from the versioned app registry;
    # if we directly import it, it'll be the wrong version
    PaymentEventType = apps.get_model("order", "PaymentEventType")
    db_alias = schema_editor.connection.alias
    event_types = [
        PaymentEventType(name="Paid (Wire Transfer)", code="paid_wt"),
        PaymentEventType(name="Paid in parts", code="paid_in_parts"),
        PaymentEventType(name="Paid in parts (Wire Transfer)", code="paid_in_parts_wt"),
        PaymentEventType(name="Refunded", code="refunded"),
    ]
    if not PaymentEventType.objects.using(db_alias).filter(name="Paid", code="paid").exists():
        # Paid event type may exist already.
        event_types.append(
            PaymentEventType(name="Paid", code="paid")
        )
    PaymentEventType.objects.using(db_alias).bulk_create(event_types)


def reverse_func(apps, schema_editor):
    # forwards_func() creates two Country instances,
    # so reverse_func() should delete them.
    PaymentEventType = apps.get_model("order", "PaymentEventType")
    db_alias = schema_editor.connection.alias
    PaymentEventType.objects.using(db_alias).filter(name="Paid", code="paid").delete()
    PaymentEventType.objects.using(db_alias).filter(name="Paid (Wire Transfer)", code="paid_wt").delete()
    PaymentEventType.objects.using(db_alias).filter(name="Paid in parts", code="paid_in_parts").delete()
    PaymentEventType.objects.using(db_alias).filter(name="Paid in parts (Wire Transfer)", code="paid_in_parts_wt").delete()
    PaymentEventType.objects.using(db_alias).filter(name="Refunded", code="refunded").delete()


class Migration(migrations.Migration):
    """
    Data Migration to create ShippingEventTypes.
    """

    dependencies = [
        ('order', '0006_add_shippingeventtype'),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]
