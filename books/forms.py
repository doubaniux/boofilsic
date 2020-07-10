from django import forms
from common.forms import KeyValueInput
from django.contrib.postgres.forms import SimpleArrayField
from django.utils.translation import gettext_lazy as _
from .models import Book, BookMark, BookReview
from common.models import MarkStatusEnum
from common.forms import RadioBooleanField, RatingValidator, TagField, TagInput
from common.forms import PreviewImageInput


def BookMarkStatusTranslator(status):
    trans_dict = {
        MarkStatusEnum.DO.value: _("在读"),
        MarkStatusEnum.WISH.value: _("想读"),
        MarkStatusEnum.COLLECT.value: _("读过")
    }
    return trans_dict[status]        


class BookForm(forms.ModelForm):
    pub_year = forms.IntegerField(required=False, max_value=9999, min_value=0, label=_("出版年份"))
    pub_month = forms.IntegerField(required=False, max_value=12, min_value=1, label=_("出版月份"))
    id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    class Meta:
        model = Book
        fields = [
            'id',
            'title',
            'isbn',
            'author',
            'pub_house',
            'subtitle',
            'translator',
            'orig_title',
            'language',
            'pub_month',
            'pub_year',
            'binding',
            'price',
            'pages',
            'cover',
            'brief',
            'contents',
            'other_info',
        ]
        labels = {
            'title': _("书名"),
            'isbn': _("ISBN"),
            'author': _("作者"),
            'pub_house': _("出版社"),
            'subtitle': _("副标题"),
            'translator': _("译者"),
            'orig_title': _("原作名"),
            'language': _("语言"),
            'pub_month': _("出版月份"),
            'pub_year': _("出版年份"),
            'binding': _("装帧"),
            'price': _("定价"),
            'pages': _("页数"),
            'cover': _("封面"),
            'brief': _("简介"),
            'contents': _("目录"),
            'other_info': _("其他信息"),
        }

        widgets = {
            'author': forms.TextInput(attrs={'placeholder': _("多个作者使用英文逗号分隔")}),
            'translator': forms.TextInput(attrs={'placeholder': _("多个译者使用英文逗号分隔")}),
            'other_info': KeyValueInput(),
            # 'cover': forms.FileInput(),
            'cover': PreviewImageInput(),
        }        

    def clean_isbn(self):
        isbn = self.cleaned_data.get('isbn')
        if isbn:
            isbn = isbn.strip()
        return isbn


class BookMarkForm(forms.ModelForm):
    IS_PRIVATE_CHOICES = [
        (True, _("仅关注者")),
        (False, _("公开")),
    ]
    STATUS_CHOICES = [(v, BookMarkStatusTranslator(v)) for v in MarkStatusEnum.values]
    id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    share_to_mastodon = forms.BooleanField(label=_("分享到长毛象"), initial=True, required=False)
    rating = forms.IntegerField(validators=[RatingValidator()], widget=forms.HiddenInput(), required=False)
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
        label = _("标签")
    )
    class Meta:
        model = BookMark
        fields = [
            'id',
            'book',
            'status',
            'rating',
            'text',
            'is_private',
        ]
        labels = {
            'rating': _("评分"),
            'text': _("短评"),
        }        
        widgets = {
            'book': forms.TextInput(attrs={"hidden": ""}),
            'text': forms.Textarea(attrs={"placeholder": _("最多只能写500字哦~")}),
        }      


class BookReviewForm(forms.ModelForm):
    IS_PRIVATE_CHOICES = [
        (True, _("仅关注者")),
        (False, _("公开")),
    ]
    share_to_mastodon = forms.BooleanField(label=_("分享到长毛象"), initial=True, required=False)    
    id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    is_private = RadioBooleanField(
        label=_("可见性"), 
        initial=True, 
        choices=IS_PRIVATE_CHOICES
    )
    class Meta:
        model = BookReview
        fields = [
            'id',
            'book',
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
            'book': forms.TextInput(attrs={"hidden": ""}),
        }


