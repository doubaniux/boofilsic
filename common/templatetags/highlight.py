from django import template
from django.utils.safestring import mark_safe
from django.template.defaultfilters import stringfilter
from django.utils.html import format_html

import re

register = template.Library()

@register.filter
@stringfilter
def highlight(text, search):
    to_be_replaced_words = set(re.findall(search, text, flags=re.IGNORECASE))

    for word in to_be_replaced_words:
        text = text.replace(word, f'<span class="highlight">{word}</span>')
    return mark_safe(text)
