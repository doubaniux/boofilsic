from django import template
from django.conf import settings
from django.template.defaultfilters import stringfilter


register = template.Library()


@register.simple_tag
def mastodon(domain):
    url = 'https://' + domain
    return url 
