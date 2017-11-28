from django.core.exceptions import ValidationError
from oscar.apps.partner import importers
from oscar.core.loading import get_class, get_classes

Partner, StockRecord = get_classes('partner.models', ['Partner',
                                                      'StockRecord'])
ProductClass, Product, Category, ProductCategory, ProductAttribute, ProductAttributeValue = get_classes(
    'catalogue.models', ('ProductClass', 'Product', 'Category',
                         'ProductCategory', 'ProductAttribute',
                         'ProductAttributeValue'))


class CatalogueImporter(importers.CatalogueImporter):
    def __init__(self, logger, delimiter=",", flush=False):
        super(CatalogueImporter, self).__init__(logger, delimiter, flush)

    def _flush_product_data(self):
        u"""Flush out product and stock models"""
        super(CatalogueImporter, self)._flush_product_data()
        ProductAttributeValue.objects.all().delete()
        ProductAttribute.objects.all().delete()

    def _import_row(self, row_number, row, stats):
        if len(row) != 5 and len(row) < 9:
            self.logger.error("Row number %d has an invalid number of fields"
                              " (%d), skipping..." % (row_number, len(row)))
            return
        item = self._create_item(*row[:5], stats=stats)
        if len(row) >= 9:
            # With stock data
            self._create_stockrecord(item, *row[5:9], stats=stats)
        if len(row) > 9:
            # With attributes.
            self._create_attributes(item, row_number, *row[9:])

    def _create_attributes(self, item, row_number, *args):
        for arg in args:
            name, value = [x.strip() for x in arg.split('-')]
            # create/get entry in ProductAttrtibute table.
            attribute, __ = ProductAttribute.objects.get_or_create(
                product_class=item.product_class,
                name=name,
                code='_'.join(name.split(' ')).lower(),
                type=ProductAttribute.TEXT  # we only allo0w text types for now.
            )
            try:
                attribute.validate_value(value)
                attribute.save_value(item, value)
            except ValidationError as e:
                self.logger.error(
                    'Attribute %s - %s in row %s for product %s, failed text type validation.',
                    name,
                    value,
                    row_number,
                    item.title
                )
