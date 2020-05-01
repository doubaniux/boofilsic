from django import template
from django.conf import settings
from django.utils.html import format_html


register = template.Library()


@register.simple_tag
def mastodon():
    url = 'https://' + settings.MASTODON_DOMAIN_NAME
    return format_html(url)    