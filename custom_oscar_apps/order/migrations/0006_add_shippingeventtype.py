# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def forwards_func(apps, schema_editor):
    # We get the model from the versioned app registry;
    # if we directly import it, it'll be the wrong version
    ShippingEventType = apps.get_model("order", "ShippingEventType")
    db_alias = schema_editor.connection.alias
    ShippingEventType.objects.using(db_alias).bulk_create([
        ShippingEventType(name="Shipped", code="shipped"),
        ShippingEventType(name="Cancelled", code="cancelled"),
        ShippingEventType(name="Returned", code="returned"),
    ])


def reverse_func(apps, schema_editor):
    # forwards_func() creates two Country instances,
    # so reverse_func() should delete them.
    ShippingEventType = apps.get_model("order", "ShippingEventType")
    db_alias = schema_editor.connection.alias
    ShippingEventType.objects.using(db_alias).filter(name="Shipped", code="shipped").delete()
    ShippingEventType.objects.using(db_alias).filter(name="Cancelled", code="cancelled").delete()
    ShippingEventType.objects.using(db_alias).filter(name="Returned", code="returned").delete()


class Migration(migrations.Migration):
    """
    Data Migration to create ShippingEventTypes.
    """

    dependencies = [
        ('order', '0005_update_email_length'),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]
