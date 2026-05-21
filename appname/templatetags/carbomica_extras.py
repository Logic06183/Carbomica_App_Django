"""
Template filters used across CARBOMICA templates.

Registered via {% load carbomica_extras %} at the top of any template
that needs them.
"""
from django import template

register = template.Library()


@register.filter(name='split')
def split_filter(value, separator=','):
    """
    Split a string into a list, stripping whitespace from each token and
    dropping empties. Used to turn a CSV CharField (e.g. Intervention.sdg_goals
    "7,13") into a list the template can iterate over.

    Django's built-in template language does not let you call str.split with
    arguments — {% for x in s.split:"," %} is a syntax error — so projects
    that store CSV in a CharField conventionally ship a custom split filter.
    """
    if value in (None, ''):
        return []
    return [token.strip() for token in str(value).split(separator) if token.strip()]
