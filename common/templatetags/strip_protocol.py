from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.filter(is_safe=True)
@stringfilter
def strip_protocol(value):
    """ Strip the `https://.../` part of urls"""
    if value.startswith("https://"):
        value = value.replace("https://", '')
    elif value.startswith("http://"):
        value = value.replace("http://", '')
    
    if value.endswith('/'):
        value = value[0:-1]
    return value