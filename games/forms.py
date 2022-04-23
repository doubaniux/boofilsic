from django import forms
from django.contrib.postgres.forms import SimpleArrayField
from django.utils.translation import gettext_lazy as _
from .models import Game, GameMark, GameReview, GameMarkStatusTranslation
from common.models import MarkStatusEnum
from common.forms import *


def GameMarkStatusTranslator(status):
    return GameMarkStatusTranslation[status]


class GameForm(forms.ModelForm):
    # id = forms.IntegerField(required=False, widget=forms.HiddenInput())

    other_info = JSONField(required=False, label=_("其他信息"))

    class Meta:
        model = Game
        fields = [
            'title',
            'source_site',
            'source_url',
            'other_title',
            'developer',
            'publisher',
            'release_date',
            'genre',
            'platform',
            'cover',
            'brief',
            'other_info'
        ]

        widgets = {
            'other_title': forms.TextInput(attrs={'placeholder': _("多个别名使用英文逗号分隔")}),
            'developer': forms.TextInput(attrs={'placeholder': _("多个开发商使用英文逗号分隔")}),
            'publisher': forms.TextInput(attrs={'placeholder': _("多个发行商使用英文逗号分隔")}),
            'genre': forms.TextInput(attrs={'placeholder': _("多个类型使用英文逗号分隔")}),
            'platform': forms.TextInput(attrs={'placeholder': _("多个平台使用英文逗号分隔")}),
            'cover': PreviewImageInput(),
        }


class GameMarkForm(MarkForm):

    STATUS_CHOICES = [(v, GameMarkStatusTranslator(v))
                      for v in MarkStatusEnum.values]

    status = forms.ChoiceField(
        label=_(""),
        widget=forms.RadioSelect(),
        choices=STATUS_CHOICES
    )

    class Meta:
        model = GameMark
        fields = [
            'id',
            'game',
            'status',
            'rating',
            'text',
            'visibility',
        ]
        widgets = {
            'game': forms.TextInput(attrs={"hidden": ""}),
        }


class GameReviewForm(ReviewForm):

    class Meta:
        model = GameReview
        fields = [
            'id',
            'game',
            'title',
            'content',
            'visibility'
        ]
        widgets = {
            'game': forms.TextInput(attrs={"hidden": ""}),
        }
