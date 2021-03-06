"""
Django settings for cell_again project.

Generated by 'django-admin startproject' using Django 1.10.7.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.10/ref/settings/
"""

import os
# For translating language names displayed to user.
from django.utils.translation import ugettext_lazy as _
# import all of Oscar's default settings.
from oscar.defaults import *
from oscar import OSCAR_MAIN_TEMPLATE_DIR, get_core_apps
# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
location = lambda x: os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', x)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.10/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = ''

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.flatpages',
    # oscar apps.
    'compressor',
    'widget_tweaks',
    # django-lockdown app.
    'lockdown',
    # custom search functionality, independent of solr and haystack.
    'casearch',
] + get_core_apps([
    'custom_oscar_apps.catalogue',
    'custom_oscar_apps.checkout',
    'custom_oscar_apps.dashboard.orders',
    'custom_oscar_apps.order',
    'custom_oscar_apps.partner',
    'custom_oscar_apps.payment',
    'custom_oscar_apps.promotions',
    'custom_oscar_apps.search',
    'custom_oscar_apps.shipping'
])

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',
    # oscar middlewares.
    'oscar.apps.basket.middleware.BasketMiddleware',
    # djang-lockdown middleware.
    'lockdown.middleware.LockdownMiddleware',
]

AUTHENTICATION_BACKENDS = (
    # allow customers to sign in using an email address rather than a username.
    'oscar.apps.customer.auth_backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
)

ROOT_URLCONF = 'cell_again.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            location('templates'),
            OSCAR_MAIN_TEMPLATE_DIR
        ],
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.i18n',
                'django.contrib.messages.context_processors.messages',
                # oscar context processors.
                'oscar.apps.search.context_processors.search_form',
                'oscar.apps.promotions.context_processors.promotions',
                'oscar.apps.checkout.context_processors.checkout',
                'oscar.apps.customer.notifications.context_processors.notifications',
                'oscar.core.context_processors.metadata',
                'cell_again.context_processors.stripe_data',
                'cell_again.context_processors.wiretransfer_data',
                'cell_again.context_processors.oscar_defaults',
                'cell_again.context_processors.misc_settings_data',
            ],
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ],
            'libraries': {
                'common_tags': 'templatetags.common_tags',
                'payment_tags': 'templatetags.payment_tags',
                'promotion_tags': 'templatetags.promotion_tags',
                'staticfile_versioning': 'templatetags.staticfile_versioning_tag'
            }
        },
    },
]

WSGI_APPLICATION = 'cell_again.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': '',
        'HOST': '',
        'USER': '',
        'PASSWORD': '',
        'ATOMIC_REQUESTS': True,
    }
}



# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = 'en'
# Language options.
LANGUAGES = [
    ('en', _('English')),
    # ('es', _('Spanish')),
]

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, '..', 'public')
STATICFILES_DIRS = (
    os.path.join(BASE_DIR, "static"),
)

MEDIA_URL = '/media/'
MEDIA_ROOT = location('media')
# django email configurations.
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
# HayStack configurations.
HAYSTACK_CONNECTIONS = {
    'default': {
        # 'ENGINE': 'haystack.backends.solr_backend.SolrEngine',
        # 'URL': 'http://127.0.0.1:8983/solr',
        # 'INCLUDE_SPELLING': True,
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',
    },
}
# oscar configurations.
OSCAR_SHOP_NAME = 'CellAgain'
OSCAR_DEFAULT_CURRENCY = 'USD'
OSCAR_DEFAULT_CURRENCY_LOWEST_VALUE = 100  # $1.
OSCAR_ALLOW_ANON_REVIEWS = False
OSCAR_HIDDEN_FEATURES = ['reviews']
# http://django-oscar.readthedocs.io/en/releases-1.4/ref/settings.html#oscar-eager-alerts
OSCAR_EAGER_ALERTS = False
OSCAR_FROM_EMAIL = 'sales@cellagain.com'
# Address settings
OSCAR_REQUIRED_ADDRESS_FIELDS = (
    'first_name', 'last_name', 'line1',
    'line4', 'state', 'postcode',
    'country', 'phone_number'
)
# oscar order pipelining.
OSCAR_INITIAL_ORDER_STATUS = 'New (Awaiting Approval)'
OSCAR_APPROVED_ORDER_STATUS = 'Approved (Awaiting Payment)'
OSCAR_FREEZE_ORDER_STATUS = 'Payment In Progress'
OSCAR_AWAITING_WIRE_TRANSFER_STATUS = 'Awaiting Wire Transfer'
OSCAR_PAID_ORDER_STATUS = 'Paid'
OSCAR_ORDER_STATUS_PIPELINE = {
    'New (Awaiting Approval)': ('Approved (Awaiting Payment)', 'Cancelled', 'Fraudulent'),
    'Approved (Awaiting Payment)': ('Payment In Progress', 'Awaiting Wire Transfer', 'Paid', 'Cancelled', 'Fraudulent'),
    'Payment In Progress': ('Approved (Awaiting Payment)', 'Paid', 'Cancelled', 'Fraudulent'),
    'Awaiting Wire Transfer': ('Approved (Awaiting Payment)', 'Paid', 'Cancelled', 'Fraudulent'),
    'Paid': ('Shipped', 'Cancelled', 'Fraudulent'),
    'Shipped': (),
    'Cancelled': (),
    'Fraudulent': (),
}
OSCAR_INITIAL_LINE_STATUS = 'Pending'
OSCAR_CANNOT_DELETE_LINE_STATUSES = ('Shipped', 'Cancelled')
OSCAR_LINE_STATUS_PIPELINE = {
    'Pending': ('Being processed', 'Cancelled',),
    'Being processed': ('Shipped', 'Cancelled',),
    'Shipped': (),
    'Cancelled': (),
}
# cascade order status changes to lines.
# it defines the status, lines must move to when
# order attains a status.
OSCAR_ORDER_STATUS_CASCADE = {
    'Paid': 'Being processed',
    'Shipped': 'Shipped',
    'Cancelled': 'Cancelled',
    'Fraudulent': 'Cancelled'
}
# Search facets.
# used when any search engine (Solr, ElasticSearch, Whoosh) is used.
OSCAR_SEARCH_FACETS = {
    'fields': OrderedDict([
        # The key for these dicts will be used when passing facet data
        # to the template. Same for the 'queries' dict below.
        # for now hide it. we can filter based on categories.
        # ('product_class', {'name': _('Type'), 'field': 'product_class'}),
        ('grading', {'name': _('Grade'), 'field': 'grading'}),
        ('carrier', {'name': _('Carrier'), 'field': 'carrier'}),
        # You can specify an 'options' element that will be passed to the
        # SearchQuerySet.facet() call.  It's hard to get 'missing' to work
        # correctly though as of Solr's hilarious syntax for selecting
        # items without a specific facet:
        # http://wiki.apache.org/solr/SimpleFacetParameters#facet.method
        # 'options': {'missing': 'true'}
    ]),
    'queries': OrderedDict([
        ('price_range',
         {
             'name': _('Price range'),
             'field': 'price',
             'queries': [
                 # This is a list of (name, query) tuples where the name will
                 # be displayed on the front-end.
                 (_('0 to 200'), u'[0 TO 200]'),
                 (_('201 to 500'), u'[201 TO 500]'),
                 (_('500+'), u'[500 TO *]'),
             ]
         }),
    ]),
}
# cellagain custom oscar configurations.
# these are not available in oscar defaults.py.
OSCAR_MIN_BASKET_QUANTITY_THRESHOLD_WHOLESALE = 5
OSCAR_FIXED_PRICE_SHIPPING_CHG_EXCL_TAX = '15.00'
OSCAR_FIXED_PRICE_SHIPPING_CHG_INCL_TAX = '30.00'
# stripe configurations.
STRIPE_SECRET_KEY = ''
STRIPE_PUBLIC_KEY = ''
# a processing fee we need to pay for the use of payment processor/gateway.
# hence we add this fee to the order as a tax.
PAYMENT_PROCESSING_FEE = '0.035'  # 3.5%.
# state wise sales tax in US.
# used with US strategy class.
US_STATE_WISE_SALES_TAX = {
    'tx': '0.0625',  # 6.25%.
    'texas': '0.0625',  # 6.25%.
}
WIRE_TRANSFER_DETAILS = (
    'Bank: Chase<br />'
    'Account Number: 12345678<br />'
    'Routing Number: Chase123<br />'
    'Description: Kindly do the transfer immediately for the order to be processed. Your Order will remain in Awaiting Payment state until we receive your payment.<br />'
)
# our billing address used in invoices.
COMPANY_BILLING_ADDRESS = (
    'CellAgain<br />'
    '3304 Timberglen Dr<br />'
    'Imperial, Pa 15126'
)
# livechat configurations.
# if empty or None livechat is considered to be disabled in site.
LIVECHAT_ID = ''
# django-lockdown configurations.
LOCKDOWN_ENABLED = False
LOCKDOWN_MESSAGE_HEADER = 'Site is under maintenance.'
LOCKDOWN_MESSAGE = 'We have locked down for maintenance and will be back shortly.'
# logging configurations.
import logging

logging.captureWarnings(True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(lineno)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(asctime)s %(message)s'
        },
        'django.server': {
            '()': 'django.utils.log.ServerFormatter',
            'format': '[%(server_time)s] %(message)s',
        }
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'django.server': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'django.server',
        },
        'py.warnings': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'formatter': 'simple',
            'filename': '/var/log/warnings.log'
        },
        'oscar.checkout': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'formatter': 'simple',
            'filename': '/var/log/checkout.log'
        },
        'oscar.catalogue.import': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'formatter': 'simple',
            'filename': os.path.join(BASE_DIR, 'catalogue_import.log')
        },
        'stripe': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'formatter': 'simple',
            'filename': '/var/log/stripe.log'
        }
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'propagate': True,
            'level': 'INFO',
        },
        'django.server': {
            'handlers': ['django.server'],
            'propagate': False,
            'level': 'INFO',
        },
        'py.warnings': {
            'handlers': ['py.warnings'],
            'propagate': True,
            'level': 'INFO',
        },
        'stripe': {
            'handlers': ['stripe'],
            'propagate': True,
            'level': 'INFO',
        },
        'oscar.checkout': {
            'handlers': ['oscar.checkout'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'oscar.catalogue.import': {
            'handlers': ['oscar.catalogue.import'],
            'propagate': True,
            'level': 'DEBUG',
        }
    }
}
