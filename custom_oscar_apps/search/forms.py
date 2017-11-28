from django import forms
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model, get_class

Product = get_model('catalogue',  'product')
is_solr_supported = get_class('search.features', 'is_solr_supported')

if not is_solr_supported():
    get_price_range_tuple = get_class('search.utils', 'get_price_range_tuple')

    class SearchForm(forms.Form):
        def __init__(self, *args, **kwargs):
            super(SearchForm, self).__init__(*args, **kwargs)

            grades = []
            carriers = []
            for p in Product.browsable.all():
                grade_attrs = p.attribute_values.filter(attribute__code__exact='grade')
                carrier_attrs = p.attribute_values.filter(attribute__code__exact='carrier')
                grades.extend(grade_attrs)
                carriers.extend(carrier_attrs)

            self.fields['grade'].choices = list(
                set(
                    [(g.value, g.value) for g in sorted(grades, key=lambda x: x.value.lower())]
                )
            )
            self.fields['carrier'].choices = list(
                set(
                    [(c.value, c.value) for c in sorted(carriers, key=lambda y: y.value.lower())]
                )
            )

        q = forms.CharField(
            required=False, label=_('Search'),
            widget=forms.HiddenInput()
        )

        # Search
        NEWEST = "-date_created"
        PRICE_HIGH_TO_LOW = "-price"
        PRICE_LOW_TO_HIGH = "price"
        TITLE_A_TO_Z = "title"
        TITLE_Z_TO_A = "-title"

        SORT_BY_CHOICES = [
            (NEWEST, _("Newest")),
            (PRICE_HIGH_TO_LOW, _("Price high to low")),
            (PRICE_LOW_TO_HIGH, _("Price low to high")),
            (TITLE_A_TO_Z, _("Title A to Z")),
            (TITLE_Z_TO_A, _("Title Z to A")),
        ]

        sort_by = forms.ChoiceField(
            label=_("Sort by"), choices=SORT_BY_CHOICES,
            widget=forms.Select(), required=False)

        min_price = forms.IntegerField(
            initial=0,
            widget=forms.NumberInput(attrs={'class': 'form-control'}),
            required=False
        )
        max_price = forms.IntegerField(
            initial=500,
            widget=forms.NumberInput(attrs={'class': 'form-control'}),
            required=False
        )

        grade = forms.MultipleChoiceField(
            label=_('Grade'),
            choices=[],
            required=False,
            widget=forms.CheckboxSelectMultiple()
        )
        carrier = forms.MultipleChoiceField(
            label=_('Carrier'),
            choices=[],
            required=False,
            widget=forms.CheckboxSelectMultiple()
        )
else:
    get_class('search.forms', 'SearchForm')
