from django import forms
from markdownx.fields import MarkdownxFormField
import django.contrib.postgres.forms as postgres
from django.utils import formats
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import json
from .models import *


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = [
            'id',
            'item',
            'title',
            'body',
            'visibility'
        ]
        widgets = {
            'item': forms.TextInput(attrs={"hidden": ""}),
        }
    title = forms.CharField(label=_("评论标题"))
    body = MarkdownxFormField(label=_("评论正文 (Markdown)"))
    share_to_mastodon = forms.BooleanField(
        label=_("分享到联邦网络"), initial=True, required=False)
    id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    visibility = forms.TypedChoiceField(
        label=_("可见性"),
        initial=0,
        coerce=int,
        choices=VisibilityType.choices,
        widget=forms.RadioSelect
    )
