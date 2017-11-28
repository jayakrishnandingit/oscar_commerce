from django import template

register = template.Library()


@register.simple_tag(name='subtract')
def subtract(value, to_subtract):
    return int(round(value, 2) - round(to_subtract, 2))
