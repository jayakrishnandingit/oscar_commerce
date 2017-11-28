from django.utils.translation import ugettext_lazy as _
from django.core.paginator import InvalidPage
from django.contrib import messages
from django.shortcuts import redirect
from oscar.apps.catalogue import views


class CatalogueView(views.CatalogueView):
    def get(self, request, *args, **kwargs):
        try:
            self.search_handler = self.get_search_handler(
                request, request.GET, request.get_full_path(), [])
        except InvalidPage:
            # Redirect to page one.
            messages.error(request, _('The given page number was invalid.'))
            return redirect('catalogue:index')
        return super(views.CatalogueView, self).get(request, *args, **kwargs)


class ProductCategoryView(views.ProductCategoryView):
    def get(self, request, *args, **kwargs):
        # Fetch the category; return 404 or redirect as needed
        self.category = self.get_category()
        potential_redirect = self.redirect_if_necessary(
            request.path, self.category)
        if potential_redirect is not None:
            return potential_redirect

        try:
            self.search_handler = self.get_search_handler(
                request, request.GET, request.get_full_path(), self.get_categories())
        except InvalidPage:
            messages.error(request, _('The given page number was invalid.'))
            return redirect(self.category.get_absolute_url())

        return super(views.ProductCategoryView, self).get(request, *args, **kwargs)
