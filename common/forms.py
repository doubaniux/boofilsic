from django import forms
import django.contrib.postgres.forms as postgres
from django.utils import formats
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import json


class KeyValueInput(forms.Widget):
    template_name = 'widgets/key_value.html'

    def get_context(self, name, value, attrs):
        """ called when rendering """
        context = {}
        context['widget'] = {
            'name': name,
            'is_hidden': self.is_hidden,
            'required': self.is_required,
            'value': self.format_value(value),
            'attrs': self.build_attrs(self.attrs, attrs),
            'template_name': self.template_name,
            'keyvalue_pairs': {},
        }
        if context['widget']['value']:
            key_value_pairs = json.loads(context['widget']['value'])
            # for kv in key_value_pairs:
            context['widget']['keyvalue_pairs'] = key_value_pairs
        return context

    class Media:
        js = ('js/key_value_input.js',)


class JSONField(postgres.JSONField):
    widget = KeyValueInput
    def to_python(self, value):
        if not value:
            return None
        json = {}
        if isinstance(value, dict):
            json = value
        else:
            pairs = eval(value)
            if isinstance(pairs, dict):
                json = pairs
            else:
                # list or tuple
                for pair in pairs:
                    json = {**json, **pair}
        return super().to_python(json)


class RadioBooleanField(forms.ChoiceField):
    widget = forms.RadioSelect

    def to_python(self, value):
        """Return a Python boolean object."""
        # Explicitly check for the string 'False', which is what a hidden field
        # will submit for False. Also check for '0', since this is what
        # RadioSelect will provide. Because bool("True") == bool('1') == True,
        # we don't need to handle that explicitly.
        if isinstance(value, str) and value.lower() in ('false', '0'):
            value = False
        else:
            value = bool(value)
        return value


class RatingValidator:
    """ empty value is not validated """
    def __call__(self, value):
        if not isinstance(value, int):
            raise ValidationError(
                _('%(value)s is not an integer'),
                params={'value': value},
            )
        if not str(value) in [str(i) for i in range(1, 11)]:
            raise ValidationError(
                _('%(value)s is not an integer in range 1-10'),
                params={'value': value},
            )


class PreviewImageInput(forms.FileInput):
    template_name = 'widgets/image.html'
    def format_value(self, value):
        """
        Return the file object if it has a defined url attribute.
        """
        if self.is_initial(value):
            if value.url:
                return value.url
            else:
                return

    def is_initial(self, value):
        """
        Return whether value is considered to be initial value.
        """
        return bool(value and getattr(value, 'url', False))


class TagInput(forms.TextInput):
    """
    Dump tag queryset into tag list
    """
    template_name = 'widgets/tag.html'
    def format_value(self, value):
        if value == '' or value is None or len(value) == 0:
            return ''
        tag_list = []
        try:
            tag_list = [t['content'] for t in value]
        except TypeError:
            tag_list = [t.content for t in value]
        # return ','.join(tag_list)
        return tag_list

    class Media:
        css = {
            'all': ('lib/css/tag-input.css',)
        }
        js = ('lib/js/tag-input.js',)
        

class TagField(forms.CharField):
    """
    Split comma connected string into tag list
    """
    widget = TagInput
    def to_python(self, value):
        value = super().to_python(value)
        if not value:
            return
        return [t.strip() for t in value.split(',')]


class MultiSelect(forms.SelectMultiple):
    template_name = 'widgets/multi_select.html'

    class Media:
        css = {
            'all': ('lib/css/multiple-select.min.css',)
        }
        js = ('lib/js/multiple-select.min.js',)


class HstoreInput(forms.Widget):
    template_name = 'widgets/hstore.html'

    def format_value(self, value):
        """
        Return a value as it should appear when rendered in a template.
        """
        if value == '' or value is None:
            return None
        if self.is_localized:
            return formats.localize_input(value)
        return value

    class Media:
        js = ('js/key_value_input.js',)


class HstoreField(forms.CharField):
    widget = HstoreInput
    def to_python(self, value):
        if not value:
            return None
        # already in python types
        if isinstance(value, list):
            return value
        pairs = eval(value)
        if len(pairs) == 1:
            pairs = (pairs,)
        return pairs
