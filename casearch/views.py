from django.shortcuts import render
from django.views import View
from django.conf import settings
from django.core.paginator import Paginator
from oscar.core.loading import get_class, get_model

Product = get_model('catalogue', 'product')
Selector = get_class('partner.strategy', 'Selector')
SearchForm = get_class('search.forms', 'SearchForm')


# Create your views here.
class IndexView(View):
    form_class = SearchForm
    template_name = 'casearch/results.html'
    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        form = SearchForm(request.GET)
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', settings.OSCAR_PRODUCTS_PER_PAGE))
        if not page:
            page = 1
        if not per_page:
            per_page = settings.OSCAR_PRODUCTS_PER_PAGE

        # @see: catalogue.managers.
        # get only non-canonical products.
        products = Product.browsable.all()
        ordered = False
        product_list = []
        if request.GET.get('q') or len(request.GET.getlist('grade', [])) > 0 or \
                len(request.GET.getlist('carrier', [])) > 0 or \
                request.GET.get('min_price') or request.GET.get('max_price') or \
                request.GET.get('sort_by'):

            if request.GET.get('q'):
                products = products.filter(title__icontains=request.GET.get('q'))

            if len(request.GET.getlist('grade', [])) > 0:
                products = products.filter(attribute_values__value_text__in=request.GET.getlist('grade', []))

            if len(request.GET.getlist('carrier', [])) > 0:
                products = products.filter(attribute_values__value_text__in=request.GET.getlist('carrier', []))

            if request.GET.get('sort_by'):
                # explicitly sepcified an order.
                if 'price' not in request.GET.get('sort_by'):
                    # we sort by pricing differently.
                    products = products.order_by(request.GET.get('sort_by'))
            else:
                products = products.order_by('-date_updated')

            product_list = list(products)
            # filter on price range.
            strategy = Selector().strategy(request)
            for product in products:
                purchase_info = strategy.fetch_for_product(product)
                # set price for sorting later.
                product.price = float(purchase_info.price.excl_tax) if purchase_info.price.excl_tax else None
                if request.GET.get('min_price') or request.GET.get('max_price'):
                    # if searched by price range and product price is unknown,
                    # we exclude the product from result.
                    if not product.price:
                        product_list.remove(product)
                if request.GET.get('min_price'):
                    if product.price and product.price < float(request.GET.get('min_price')):
                        product_list.remove(product)
                if request.GET.get('max_price'):
                    if product.price and product.price > float(request.GET.get('max_price')):
                        product_list.remove(product)
            # sort by pricing.
            if '-price' in request.GET.get('sort_by', ''):
                # sort by descending order.
                product_list = sorted(product_list, key=lambda p: p.price, reverse=True)
            elif 'price' in request.GET.get('sort_by', ''):
                # sort by ascending order.
                product_list = sorted(product_list, key=lambda p: p.price)
        else:
            product_list = list(products)

        paginator = Paginator(product_list, per_page)
        try:
            product_list = paginator.page(page)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            product_list = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            product_list = paginator.page(paginator.num_pages)

        context = {
            'query': request.GET.get('q', ''),
            'search_form': form,
            'paginator': paginator,
            'page': product_list
        }
        return render(request, self.template_name, context)
