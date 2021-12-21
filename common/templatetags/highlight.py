from django import template
from django.utils.safestring import mark_safe
from django.template.defaultfilters import stringfilter
from django.utils.html import format_html

import re

register = template.Library()

@register.filter
@stringfilter
def highlight(text, search):
    return mark_safe(text.replace(search, f'<span class="highlight">{search}</span>'))  # TODO better query words match
