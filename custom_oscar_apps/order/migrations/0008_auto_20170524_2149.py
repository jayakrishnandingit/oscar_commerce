# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-05-24 16:19
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0007_add_paymenteventtype'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_method',
            field=models.CharField(blank=True, max_length=128, verbose_name='Payment method'),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_method_code',
            field=models.CharField(blank=True, default=b'', max_length=128),
        ),
    ]