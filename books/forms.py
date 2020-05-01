from django import forms
from common.forms import KeyValueInput
from django.contrib.postgres.forms import SimpleArrayField
from django.utils.translation import gettext_lazy as _
from .models import Book, BookMark, BookReview


class BookForm(forms.ModelForm):
    pub_year = forms.IntegerField(required=False, max_value=9999, min_value=0, label=_("出版年份"))
    pub_month = forms.IntegerField(required=False, max_value=12, min_value=1, label=_("出版月份"))
    class Meta:
        model = Book
        fields = [
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
            'other_info': _("其他信息"),
        }
        widgets = {
            'author': forms.TextInput(attrs={'placeholder': _("多个作者使用英文逗号分隔")}),
            'translator': forms.TextInput(attrs={'placeholder': _("多个译者使用英文逗号分隔")}),
            'other_info': KeyValueInput(),
        }        


class BookMarkForm(forms.ModelForm):
    class Meta:
        model = BookMark
        fields = [
            'book',
            'status',
            'rating',
            'text',
            'is_private',
        ]


class BookReviewForm(forms.ModelForm):
    class Meta:
        model = BookReview
        fields = [
            'book',
            'title',
            'content',
            'is_private'
        ]