from django import template
from collection.models import Collection


register = template.Library()


@register.simple_tag(takes_context=True)
def current_user_marked_item(context, item):
    # NOTE weird to put business logic in tags
    user = context['request'].user
    if user and user.is_authenticated:
        if isinstance(item, Collection) and item.owner == user:
            return item
        else:
            return context['request'].user.get_mark_for_item(item)
    return None


