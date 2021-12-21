from django import forms
from django.contrib.postgres.forms import SimpleArrayField
from django.utils.translation import gettext_lazy as _
from .models import Collection
from common.models import MarkStatusEnum
from common.forms import *


class CollectionForm(forms.ModelForm):
    # id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    name = forms.CharField(label=_("标题"))
    description = MarkdownxFormField(label=_("正文 (Markdown)"))

    class Meta:
        model = Collection
        fields = [
            'name',
            'description',
            'cover',
        ]

        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _("收藏单名称")}),
            'developer': forms.TextInput(attrs={'placeholder': _("多个开发商使用英文逗号分隔")}),
            'publisher': forms.TextInput(attrs={'placeholder': _("多个发行商使用英文逗号分隔")}),
            'genre': forms.TextInput(attrs={'placeholder': _("多个类型使用英文逗号分隔")}),
            'platform': forms.TextInput(attrs={'placeholder': _("多个平台使用英文逗号分隔")}),
            'cover': PreviewImageInput(),
        }
