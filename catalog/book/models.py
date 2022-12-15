"""
Models for Book

Series -> Work -> Edition

Series is not fully implemented at the moment

Goodreads
Famous works have many editions

Google Books:
only has Edition level ("volume") data

Douban:
old editions has only CUBN(Chinese Unified Book Number)
work data seems asymmetric (a book links to a work, but may not listed in that work as one of its editions)

"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from catalog.common import *
from .utils import *


class Edition(Item):
    category = ItemCategory.Book
    url_path = 'book'
    isbn = PrimaryLookupIdDescriptor(IdType.ISBN)
    asin = PrimaryLookupIdDescriptor(IdType.ASIN)
    cubn = PrimaryLookupIdDescriptor(IdType.CUBN)
    # douban_book = LookupIdDescriptor(IdType.DoubanBook)
    # goodreads = LookupIdDescriptor(IdType.Goodreads)

    METADATA_COPY_LIST = [
        'title',
        'brief',
        # legacy fields
        'subtitle',
        'orig_title',
        'author',
        'translator',
        'language',
        'pub_house',
        'pub_year',
        'pub_month',
        'binding',
        'price',
        'pages',
        'contents',
        'series',
        'producer',
    ]
    subtitle = jsondata.CharField(null=True, blank=True, default=None)
    orig_title = jsondata.CharField(null=True, blank=True, default=None)
    author = jsondata.ArrayField(_('作者'), null=False, blank=False, default=list)
    translator = jsondata.ArrayField(_('译者'), null=True, blank=True, default=list)
    language = jsondata.ArrayField(_("语言"), null=True, blank=True, default=list)
    pub_house = jsondata.ArrayField(_('出版方'), null=True, blank=True, default=list)
    pub_year = jsondata.IntegerField(_("发表年份"), null=True, blank=True)
    pub_month = jsondata.IntegerField(_("发表月份"), null=True, blank=True)
    binding = jsondata.CharField(null=True, blank=True, default=None)
    pages = jsondata.IntegerField(blank=True, default=None)
    series = jsondata.CharField(null=True, blank=True, default=None)
    contents = jsondata.CharField(null=True, blank=True, default=None)
    price = jsondata.FloatField(_("发表月份"), null=True, blank=True)
    producer = jsondata.FloatField(_("发表月份"), null=True, blank=True)

    @property
    def isbn10(self):
        return isbn_13_to_10(self.isbn)

    @isbn10.setter
    def isbn10(self, value):
        self.isbn = isbn_10_to_13(value)

    def update_linked_items_from_external_resource(self, resource):
        """add Work from resource.metadata['work'] if not yet"""
        links = resource.required_resources + resource.related_resources
        for w in links:
            if w['model'] == 'Work':
                work = Work.objects.filter(primary_lookup_id_type=w['id_type'], primary_lookup_id_value=w['id_value']).first()
                if work and work not in self.works.all():
                    self.works.add(work)
                # if not work:
                #     _logger.info(f'Unable to find link for {w["url"]}')


class Work(Item):
    category = ItemCategory.Book
    url_path = 'book/work'
    douban_work = PrimaryLookupIdDescriptor(IdType.DoubanBook_Work)
    goodreads_work = PrimaryLookupIdDescriptor(IdType.Goodreads_Work)
    editions = models.ManyToManyField(Edition, related_name='works')


class Series(Item):
    category = ItemCategory.Book
    url_path = 'book/series'
    # douban_serie = LookupIdDescriptor(IdType.DoubanBook_Serie)
    # goodreads_serie = LookupIdDescriptor(IdType.Goodreads_Serie)

    class Meta:
        proxy = True
