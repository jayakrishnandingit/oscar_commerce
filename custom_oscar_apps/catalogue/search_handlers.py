from django.conf import settings
from django.views.generic.list import MultipleObjectMixin
from oscar.core.loading import get_class, get_model

Product = get_model('catalogue', 'Product')
SearchForm = get_class('search.forms', 'SearchForm')
Selector = get_class('partner.strategy', 'Selector')


class SimpleProductSearchHandler(MultipleObjectMixin):
    """
    A basic implementation overriding the full-featured Oscar SearchHandler to add
    faceting support, but doesn't require a Haystack backend.
    It supports category browsing too.

    Note that is meant as a replacement search handler and not as a view
    mixin; the mixin just does most of what we need it to do.
    """
    paginate_by = settings.OSCAR_PRODUCTS_PER_PAGE
    form_class = SearchForm

    def __init__(self, request, request_data, full_path, categories=None):
        self.request = request
        self.categories = categories
        self.request_data = request_data
        self.kwargs = {'page': request_data.get('page', 1)}
        self.object_list = self.get_queryset()
        self.form = self.form_class(request_data)

    def get_ordering(self):
        if self.request_data.get('sort_by'):
            # explicitly sepcified an order.
            if 'price' not in self.request_data.get('sort_by'):
                # we sort by pricing differently.
                self.request_data.get('sort_by')
        else:
            '-date_updated'

    def get_ordered_by_price(self, product_list, sort_by):
        if sort_by:
            if '-price' in sort_by:
                # sort by descending order.
                product_list = sorted(product_list, key=lambda p: p.price, reverse=True)
            elif 'price' in sort_by:
                # sort by ascending order.
                product_list = sorted(product_list, key=lambda p: p.price)
        return product_list

    def get_queryset(self):
        qs = Product.browsable.base_queryset()
        product_list = []
        if self.categories:
            qs = qs.filter(categories__in=self.categories).distinct()
        # form filters.
        if self.request_data.get('q') or len(self.request_data.getlist('grade', [])) > 0 or \
                len(self.request_data.getlist('carrier', [])) > 0:

            if self.request_data.get('q'):
                qs = qs.filter(title__icontains=self.request_data.get('q'))

            if len(self.request_data.getlist('grade', [])) > 0:
                qs = qs.filter(attribute_values__value_text__in=self.request_data.getlist('grade'))

            if len(self.request_data.getlist('carrier', [])) > 0:
                qs = qs.filter(attribute_values__value_text__in=self.request_data.getlist('carrier'))
        # ordering.
        ordering = self.get_ordering()
        if ordering:
            if isinstance(ordering, six.string_types):
                ordering = (ordering,)
            qs = qs.order_by(*ordering)

        product_list = list(qs)
        # filter on price range.
        strategy = Selector().strategy(self.request)
        for product in qs:
            purchase_info = strategy.fetch_for_product(product)
            product.price = float(purchase_info.price.excl_tax) if purchase_info.price.excl_tax else None
            if self.request_data.get('min_price') or self.request_data.get('max_price'):
                # if searched by price range and product price is unknown,
                # we exclude the product from result.
                if not product.price:
                    product_list.remove(product)
            if self.request_data.get('min_price'):
                if product.price and product.price < float(self.request_data.get('min_price')):
                    product_list.remove(product)
            if self.request_data.get('max_price'):
                if product.price and product.price > float(self.request_data.get('max_price')):
                    product_list.remove(product)

        # sort by price.
        product_list = self.get_ordered_by_price(product_list, self.request_data.get('sort_by'))

        return product_list

    def get_search_context_data(self, context_object_name):
        # Set the context_object_name instance property as it's needed
        # internally by MultipleObjectMixin
        self.context_object_name = context_object_name
        context = self.get_context_data(object_list=self.object_list)
        context[context_object_name] = context['page_obj'].object_list
        context['form'] = self.form
        return context
