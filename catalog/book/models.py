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
work data seems asymmetric (a book page links to a work page, but may not listed on that work page as one of the editions)

"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from catalog.common import *
from .utils import *


class Edition(Item):
    isbn = PrimaryLookupIdDescriptor(IdType.ISBN)
    asin = PrimaryLookupIdDescriptor(IdType.ASIN)
    cubn = PrimaryLookupIdDescriptor(IdType.CUBN)
    # douban_book = LookupIdDescriptor(IdType.DoubanBook)
    # goodreads = LookupIdDescriptor(IdType.Goodreads)
    languages = jsondata.ArrayField(_("语言"), null=True, blank=True, default=list)
    publish_year = jsondata.IntegerField(_("发表年份"), null=True, blank=True)
    publish_month = jsondata.IntegerField(_("发表月份"), null=True, blank=True)
    pages = jsondata.IntegerField(blank=True, default=None)
    authors = jsondata.ArrayField(_('作者'), null=False, blank=False, default=list)
    translaters = jsondata.ArrayField(_('译者'), null=True, blank=True, default=list)
    publishers = jsondata.ArrayField(_('出版方'), null=True, blank=True, default=list)

    @property
    def isbn10(self):
        return isbn_13_to_10(self.isbn)

    @isbn10.setter
    def isbn10(self, value):
        self.isbn = isbn_10_to_13(value)

    def update_linked_items_from_extenal_page(self, page):
        """add Work from page.metadata['work'] if not yet"""
        w = page.metadata.get('work', None)
        if w:
            work = Work.objects.filter(primary_lookup_id_type=w['lookup_id_type'], primary_lookup_id_value=w['lookup_id_value']).first()
            if work:
                if any(edition == self for edition in work.editions.all()):
                    return
            else:
                work = Work.objects.create(primary_lookup_id_type=w['lookup_id_type'], primary_lookup_id_value=w['lookup_id_value'], title=w['title'])
            work.editions.add(self)


class Work(Item):
    # douban_work = PrimaryLookupIdDescriptor(IdType.DoubanBook_Work)
    # goodreads_work = PrimaryLookupIdDescriptor(IdType.Goodreads_Work)
    editions = models.ManyToManyField(Edition, related_name='works')  # , through='WorkEdition'

    # def __str__(self):
    #     return self.title

    # class Meta:
    #     proxy = True


class Series(Item):
    # douban_serie = LookupIdDescriptor(IdType.DoubanBook_Serie)
    # goodreads_serie = LookupIdDescriptor(IdType.Goodreads_Serie)

    class Meta:
        proxy = True
