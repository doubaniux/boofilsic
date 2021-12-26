from django import forms
from django.contrib.postgres.forms import SimpleArrayField
from django.utils.translation import gettext_lazy as _
from .models import Collection
from common.forms import *


class CollectionForm(forms.ModelForm):
    # id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    title = forms.CharField(label=_("标题"))
    description = MarkdownxFormField(label=_("详细介绍 (Markdown)"))
    share_to_mastodon = forms.BooleanField(
        label=_("分享到联邦网络"), initial=True, required=False)
    visibility = forms.TypedChoiceField(
        label=_("可见性"),
        initial=0,
        coerce=int,
        choices=VISIBILITY_CHOICES,
        widget=forms.RadioSelect
    )

    class Meta:
        model = Collection
        fields = [
            'title',
            'description',
            'cover',
            'visibility',
        ]

        widgets = {
            'cover': PreviewImageInput(),
        }
