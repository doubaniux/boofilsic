from django import forms
from django.contrib.postgres.forms import JSONField
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

            context['widget']['keyvalue_pairs'] = {

            }
        return context

