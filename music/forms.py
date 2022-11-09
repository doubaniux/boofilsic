from django import forms
from django.contrib.postgres.forms import SimpleArrayField
from django.utils.translation import gettext_lazy as _
from .models import *
from common.models import MarkStatusEnum
from common.forms import *


def MusicMarkStatusTranslator(status):
    return MusicMarkStatusTranslation[status]


class SongForm(forms.ModelForm):

    id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    other_info = JSONField(required=False, label=_("其他信息"))
    duration = DurationField(required=False)

    class Meta:
        model = Song
        # fields = '__all__'
        fields = [
            'id',
            'title',
            'source_site',
            'source_url',
            'artist',
            'release_date',
            'duration',
            'isrc',
            'genre',
            'cover',
            'album',
            'brief',
            'other_info',
        ]
        widgets = {
            'artist': forms.TextInput(attrs={'placeholder': _("多个艺术家使用英文逗号分隔")}),
            'duration': forms.TextInput(attrs={'placeholder': _("毫秒")}),
            'cover': PreviewImageInput(),
        }


class SongMarkForm(MarkForm):

    STATUS_CHOICES = [(v, MusicMarkStatusTranslator(v))
                      for v in MarkStatusEnum.values]

    status = forms.ChoiceField(
        label=_(""),
        widget=forms.RadioSelect(),
        choices=STATUS_CHOICES
    )

    class Meta:
        model = SongMark
        fields = [
            'id',
            'song',
            'status',
            'rating',
            'text',
            'visibility',
        ]
        widgets = {
            'song': forms.TextInput(attrs={"hidden": ""}),
        }


class SongReviewForm(ReviewForm):

    class Meta:
        model = SongReview
        fields = [
            'id',
            'song',
            'title',
            'content',
            'visibility'
        ]
        widgets = {
            'song': forms.TextInput(attrs={"hidden": ""}),
        }

        
class AlbumForm(forms.ModelForm):

    id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    other_info = JSONField(required=False, label=_("其他信息"))
    duration = DurationField(required=False)

    class Meta:
        model = Album
        # fields = '__all__'
        fields = [
            'id',
            'title',
            'source_site',
            'source_url',
            'artist',
            'company',
            'release_date',
            'duration',
            'genre',
            'cover',
            'brief',
            'track_list',
            'other_info',
        ]
        widgets = {
            'artist': forms.TextInput(attrs={'placeholder': _("多个艺术家使用英文逗号分隔")}),
            'company': forms.TextInput(attrs={'placeholder': _("多个发行方使用英文逗号分隔")}),
            'duration': forms.TextInput(attrs={'placeholder': _("毫秒")}),
            'cover': PreviewImageInput(),
        }


class AlbumMarkForm(MarkForm):

    STATUS_CHOICES = [(v, MusicMarkStatusTranslator(v))
                      for v in MarkStatusEnum.values]

    status = forms.ChoiceField(
        label=_(""),
        widget=forms.RadioSelect(),
        choices=STATUS_CHOICES
    )

    class Meta:
        model = AlbumMark
        fields = [
            'id',
            'album',
            'status',
            'rating',
            'text',
            'visibility',
        ]
        widgets = {
            'album': forms.TextInput(attrs={"hidden": ""}),
        }


class AlbumReviewForm(ReviewForm):

    class Meta:
        model = AlbumReview
        fields = [
            'id',
            'album',
            'title',
            'content',
            'visibility'
        ]
        widgets = {
            'album': forms.TextInput(attrs={"hidden": ""}),
        }
