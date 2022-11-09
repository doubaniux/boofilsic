from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Collection
from common.forms import *


COLLABORATIVE_CHOICES = [
    (0, _("仅限创建者")),
    (1, _("创建者及其互关用户")),
]


class CollectionForm(forms.ModelForm):
    # id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    title = forms.CharField(label=_("标题"))
    description = MarkdownxFormField(label=_("详细介绍 (Markdown)"))
    # share_to_mastodon = forms.BooleanField(label=_("分享到联邦网络"), initial=True, required=False)
    visibility = forms.TypedChoiceField(
        label=_("可见性"),
        initial=0,
        coerce=int,
        choices=VISIBILITY_CHOICES,
        widget=forms.RadioSelect
    )
    collaborative = forms.TypedChoiceField(
        label=_("协作整理权限"),
        initial=0,
        coerce=int,
        choices=COLLABORATIVE_CHOICES,
        widget=forms.RadioSelect
    )

    class Meta:
        model = Collection
        fields = [
            'title',
            'description',
            'cover',
            'visibility',
            'collaborative',
        ]

        widgets = {
            'cover': PreviewImageInput(),
        }
