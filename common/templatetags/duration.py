from django import template
from django.template.defaultfilters import stringfilter
from django.utils.text import Truncator

register = template.Library()


@register.filter(is_safe=True)
@stringfilter
def duration_format(value):
    duration = int(value)
    h = duration // 3600000
    m = duration % 3600000 // 60000
    return (f"{h}小时 " if h else "") + (f"{m}分钟" if m else "")
