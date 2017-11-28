from haystack import indexes
from oscar.apps.search import search_indexes


class ProductIndex(search_indexes.ProductIndex):
    grading = indexes.CharField(null=True, faceted=True)
    carrier = indexes.CharField(null=True, faceted=True)

    def prepare_grading(self, obj):
        attrs = obj.attribute_values.filter(attribute__code__exact='grading')
        if len(attrs) > 0:
            return [attr.value_text for attr in attrs]

    def prepare_carrier(self, obj):
        attrs = obj.attribute_values.filter(attribute__code__exact='carrier')
        if len(attrs) > 0:
            return [attr.value_text for attr in attrs]
