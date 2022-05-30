from django import template
import datetime
from django.utils import timezone


register = template.Library()


@register.simple_tag(takes_context=True)
def current_user_marked_item(context, item):
    if context['request'].user and context['request'].user.is_authenticated:
        return context['request'].user.get_mark_for_item(item)
    return None


@register.filter
def prettydate(d):
    diff = timezone.now() - d
    s = diff.seconds
    if diff.days > 14 or diff.days < 0:
        return d.strftime('%Y年%m月%d日')
    elif diff.days >= 1:
        return '{} 天前'.format(diff.days)
    elif s < 120:
        return '刚刚'
    elif s < 3600:
        return '{} 分钟前'.format(s / 60)
    else:
        return '{} 小时前'.format(s / 3600)
