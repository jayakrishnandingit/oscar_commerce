"""myoscar URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import include, url
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.views.static import serve as static_serve
from django.views.i18n import JavaScriptCatalog
from django.contrib import admin
from django.conf import settings
from oscar.app import application
from oscar.core.loading import get_class

is_solr_supported = get_class('search.features', 'is_solr_supported')

urlpatterns = [
    url(r'^i18n/', include('django.conf.urls.i18n')),
    # The Django admin is not officially supported; expect breakage.
    # Nonetheless, it's often useful for debugging.
    # url(r'^admin/', admin.site.urls),
]

if not is_solr_supported():
    urlpatterns += i18n_patterns(
        # local search functionality independent of haystack. hits DB.
        url(r'^search/', include('casearch.urls', namespace='casearch')),
    )

urlpatterns += i18n_patterns(
    # oscar urls.
    url(r'', include(application.urls)),
    url(r'^jsi18n/$', JavaScriptCatalog.as_view(packages=settings.INSTALLED_APPS), name='javascript-catalog'),
)

# For development only
if settings.DEBUG:
    urlpatterns = urlpatterns + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += [
        url(r'^media/(?P<path>.*)$', static_serve, {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),
    ]
