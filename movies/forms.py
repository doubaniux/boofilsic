from django import forms
from django.contrib.postgres.forms import SimpleArrayField
from django.utils.translation import gettext_lazy as _
from .models import Movie, MovieMark, MovieReview
from common.models import MarkStatusEnum
from common.forms import RadioBooleanField, RatingValidator, TagField, TagInput
from common.forms import KeyValueInput
from common.forms import PreviewImageInput


def MovieMarkStatusTranslator(status):
    trans_dict = {
        MarkStatusEnum.DO.value: _("在看"),
        MarkStatusEnum.WISH.value: _("想看"),
        MarkStatusEnum.COLLECT.value: _("看过")
    }
    return trans_dict[status]


class MovieForm(forms.ModelForm):
    # pub_year = forms.IntegerField(
    #     required=False, max_value=9999, min_value=0, label=_("出版年份"))
    # pub_month = forms.IntegerField(
    #     required=False, max_value=12, min_value=1, label=_("出版月份"))
    id = forms.IntegerField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Movie
        fields = [
            'id',
            'title',
            'orig_title',
            'other_title',
            'imbd_code',
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
            'brief',
            'is_series',
        ]
        labels = {
            'title': _("标题"),
            'orig_title': _("原名"),
            'other_title': _("又名"),
            'imbd_code': _("IMBd编号"),
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
            'is_series': _("是否是剧集"),
        }

        # widgets = {
        #     'author': forms.TextInput(attrs={'placeholder': _("多个作者使用英文逗号分隔")}),
        #     'translator': forms.TextInput(attrs={'placeholder': _("多个译者使用英文逗号分隔")}),
        #     'other_info': KeyValueInput(),
        #     # 'cover': forms.FileInput(),
        #     'cover': PreviewImageInput(),
        # }

    # def clean_isbn(self):
    #     isbn = self.cleaned_data.get('isbn')
    #     if isbn:
    #         isbn = isbn.strip()
    #     return isbn


class MovieMarkForm(forms.ModelForm):
    IS_PRIVATE_CHOICES = [
        (True, _("仅关注者")),
        (False, _("公开")),
    ]
    STATUS_CHOICES = [(v, MovieMarkStatusTranslator(v))
                      for v in MarkStatusEnum.values]

    id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    share_to_mastodon = forms.BooleanField(
        label=_("分享到长毛象"), initial=True, required=False)
    rating = forms.IntegerField(
        validators=[RatingValidator()], widget=forms.HiddenInput(), required=False)
    status = forms.ChoiceField(
        label=_(""),
        widget=forms.RadioSelect(),
        choices=STATUS_CHOICES
    )
    is_private = RadioBooleanField(
        label=_("可见性"),
        initial=True,
        choices=IS_PRIVATE_CHOICES
    )
    tags = TagField(
        required=False,
        widget=TagInput(attrs={'placeholder': _("回车增加标签")}),
        label=_("标签")
    )
    text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "placeholder": _("最多只能写360字哦~"),
                "maxlength": 360
            }
        ),

        label=_("短评"),
    )

    class Meta:
        model = MovieMark
        fields = [
            'id',
            'movie',
            'status',
            'rating',
            'text',
            'is_private',
        ]
        labels = {
            'rating': _("评分"),
        }
        widgets = {
            'movie': forms.TextInput(attrs={"hidden": ""}),
        }


class MovieReviewForm(forms.ModelForm):
    IS_PRIVATE_CHOICES = [
        (True, _("仅关注者")),
        (False, _("公开")),
    ]
    share_to_mastodon = forms.BooleanField(
        label=_("分享到长毛象"), initial=True, required=False)
    id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    is_private = RadioBooleanField(
        label=_("可见性"),
        initial=True,
        choices=IS_PRIVATE_CHOICES
    )

    class Meta:
        model = MovieReview
        fields = [
            'id',
            'movie',
            'title',
            'content',
            'is_private'
        ]
        labels = {
            'book': "",
            'title': _("标题"),
            'content': _("正文"),
            'share_to_mastodon': _("分享到长毛象")
        }
        widgets = {
            'movie': forms.TextInput(attrs={"hidden": ""}),
        }
