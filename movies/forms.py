from django import forms
from django.contrib.postgres.forms import SimpleArrayField
from django.utils.translation import gettext_lazy as _
from .models import Movie, MovieMark, MovieReview, MovieGenreEnum
from common.models import MarkStatusEnum
from common.forms import *


def MovieMarkStatusTranslator(status):
    trans_dict = {
        MarkStatusEnum.DO.value: _("在看"),
        MarkStatusEnum.WISH.value: _("想看"),
        MarkStatusEnum.COLLECT.value: _("看过")
    }
    return trans_dict[status]


class MovieForm(forms.ModelForm):
    id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    genre =  forms.MultipleChoiceField(
        required=False,
        choices=MovieGenreEnum.choices, 
        widget= MultiSelect,
        label=_("类型")
    )
    showtime = HstoreField(
        required=False,
        label=_("上映时间"),
        widget=HstoreInput(
            attrs={
                'placeholder-key': _("日期"),
                'placeholder-value': _("地区"),
            }
        )
    )
    other_info = JSONField(required=False, label=_("其他信息"))

    class Meta:
        model = Movie
        fields = [
            'id',
            'title',
            'source_site',
            'source_url',
            'orig_title',
            'other_title',
            'imdb_code',
            'director',
            'playwright',
            'actor',
            'genre',
            'showtime',
            'site',
            'area',
            'language',
            'year',
            'duration',
            'season',
            'episodes',
            'single_episode_length',
            'cover',
            'is_series',
            'brief',
            'other_info',
        ]
        labels = {
            'title': _("标题"),
            'orig_title': _("原名"),
            'other_title': _("又名"),
            'imdb_code': _("IMDb编号"),
            'director': _("导演"),
            'playwright': _("编剧"),
            'actor': _("主演"),
            'genre': _("类型"),
            'showtime': _("上映时间"),
            'site': _("官方网站"),
            'area': _("国家/地区"),
            'language': _("语言"),
            'year': _("年份"),
            'duration': _("片长"),
            'season': _("季数"),
            'episodes': _("集数"),
            'single_episode_length': _("单集片长"),
            'cover': _("封面"),
            'brief': _("简介"),
            'other_info': _("其他信息"),
            'is_series': _("是否为剧集"),
        }

        widgets = {
            'other_title': forms.TextInput(attrs={'placeholder': _("多个别名使用英文逗号分隔")}),
            'director': forms.TextInput(attrs={'placeholder': _("多个导演使用英文逗号分隔")}),
            'actor': forms.TextInput(attrs={'placeholder': _("多个主演使用英文逗号分隔")}),
            'playwright': forms.TextInput(attrs={'placeholder': _("多个编剧使用英文逗号分隔")}),
            'area': forms.TextInput(attrs={'placeholder': _("多个国家/地区使用英文逗号分隔")}),
            'language': forms.TextInput(attrs={'placeholder': _("多种语言使用英文逗号分隔")}),
            'cover': PreviewImageInput(),
            'is_series': forms.CheckboxInput(attrs={'style': 'width: auto; position: relative; top: 2px'})
        }


class MovieMarkForm(MarkForm):

    STATUS_CHOICES = [(v, MovieMarkStatusTranslator(v))
                      for v in MarkStatusEnum.values]

    status = forms.ChoiceField(
        label=_(""),
        widget=forms.RadioSelect(),
        choices=STATUS_CHOICES
    )


    class Meta:
        model = MovieMark
        fields = [
            'id',
            'movie',
            'status',
            'rating',
            'text',
            'visibility',
        ]
        widgets = {
            'movie': forms.TextInput(attrs={"hidden": ""}),
        }


class MovieReviewForm(ReviewForm):

    class Meta:
        model = MovieReview
        fields = [
            'id',
            'movie',
            'title',
            'content',
            'visibility'
        ]
        widgets = {
            'movie': forms.TextInput(attrs={"hidden": ""}),
        }
