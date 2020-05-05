from django import forms
from django.contrib.postgres.forms import JSONField
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import json


class KeyValueInput(forms.Widget):
    """ jQeury required """
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
        return super().to_python(value)


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