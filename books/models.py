import uuid
import django.contrib.postgres.fields as postgres
from django.utils.translation import ugettext_lazy as _
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import reverse
from common.models import Entity, Mark, Review, Tag
from common.utils import GenerateDateUUIDMediaFilePath
from django.utils import timezone
from django.conf import settings


def book_cover_path(instance, filename):
    return GenerateDateUUIDMediaFilePath(instance, filename, settings.BOOK_MEDIA_PATH_ROOT)


class Book(Entity):
    # widely recognized name, usually in Chinese
    title = models.CharField(_("title"), max_length=200)
    subtitle = models.CharField(_("subtitle"), blank=True, default='', max_length=200)
    # original name, for books in foreign language
    orig_title = models.CharField(_("original title"), blank=True, default='', max_length=200)

    author = postgres.ArrayField(
        models.CharField(_("author"), blank=True, default='', max_length=100),
        null=True,
        blank=True,
        default=list,
    )
    translator = postgres.ArrayField(
        models.CharField(_("translator"), blank=True, default='', max_length=100),
        null=True,
        blank=True,
        default=list,
    )
    language = models.CharField(_("language"), blank=True, default='', max_length=10)
    pub_house = models.CharField(_("publishing house"), blank=True, default='', max_length=200)
    pub_year = models.IntegerField(_("published year"), null=True, blank=True)
    pub_month = models.IntegerField(_("published month"), null=True, blank=True)
    binding = models.CharField(_("binding"), blank=True, default='', max_length=50)
    # since data origin is not formatted and might be CNY USD or other currency, use char instead
    price = models.CharField(_("pricing"), blank=True, default='', max_length=50)
    pages = models.PositiveIntegerField(_("pages"), null=True, blank=True)
    isbn = models.CharField(_("ISBN"), blank=True, null=False, max_length=20, db_index=True, default='')
    # to store previously scrapped data 
    cover = models.ImageField(_("cover picture"), upload_to=book_cover_path, default=settings.DEFAULT_BOOK_IMAGE, blank=True)
    contents = models.TextField(blank=True, default="")

    class Meta:
        # more info: https://docs.djangoproject.com/en/2.2/ref/models/options/
        # set managed=False if the model represents an existing table or
        # a database view that has been created by some other means.
        # check the link above for further info
        # managed = True
        # db_table = 'book'
        constraints = [
            models.CheckConstraint(check=models.Q(pub_year__gte=0), name='pub_year_lowerbound'),
            models.CheckConstraint(check=models.Q(pub_month__lte=12), name='pub_month_upperbound'),
            models.CheckConstraint(check=models.Q(pub_month__gte=1), name='pub_month_lowerbound'),
        ]

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse("books:retrieve", args=[self.id])

    def get_tags_manager(self):
        return self.book_tags

    @property
    def verbose_category_name(self):
        return _("书籍")


class BookMark(Mark):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='book_marks', null=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'book'], name="unique_book_mark")
        ]


class BookReview(Review):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='book_reviews', null=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'book'], name="unique_book_review")
        ]    


class BookTag(Tag):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='book_tags', null=True)
    mark = models.ForeignKey(BookMark, on_delete=models.CASCADE, related_name='bookmark_tags', null=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['content', 'mark'], name="unique_bookmark_tag")
        ]
