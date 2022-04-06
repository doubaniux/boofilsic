from django import template


register = template.Library()


@register.simple_tag(takes_context=True)
def current_user_marked_item(context, item):
    return context['request'].user.get_mark_for_item(item)
