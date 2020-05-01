from django import template
from django.utils.safestring import mark_safe
from django.template.defaultfilters import stringfilter
from django.utils.html import format_html


register = template.Library()

@register.filter
@stringfilter
def highlight(text, search):
    highlighted = text.replace(search, '<span class="highlight">{}</span>'.format(search))
    return mark_safe(highlighted)