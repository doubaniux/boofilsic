from typing import *
import re
from .models import ExternalPage
from dataclasses import dataclass, field


@dataclass
class PageData:
    lookup_ids: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    cover_image = None
    cover_image_extention: str = None


class AbstractSite:
    """
    Abstract class to represent a site
    """
    ID_TYPE = None
    WIKI_PROPERTY_ID = 'P0undefined0'
    DEFAULT_MODEL = None
    URL_PATTERNS = [r"\w+://undefined/(\d+)"]

    @classmethod
    def validate_url(self, url: str):
        u = next(iter([re.match(p, url) for p in self.URL_PATTERNS if re.match(p, url)]), None)
        return u is not None

    @classmethod
    def id_to_url(self, id_value):
        return 'https://undefined/' + id_value

    @classmethod
    def url_to_id(self, url: str):
        u = next(iter([re.match(p, url) for p in self.URL_PATTERNS if re.match(p, url)]), None)
        return u[1] if u else None

    def __str__(self):
        return f'<{self.__class__.__name__}: {self.url}>'

    def __init__(self, url=None):
        self.id_value = self.url_to_id(url) if url else None
        self.url = self.id_to_url(self.id_value) if url else None
        self.page = None

    def get_page(self):
        if not self.page:
            self.page = ExternalPage.objects.filter(url=self.url).first()
            if self.page is None:
                self.page = ExternalPage(id_type=self.ID_TYPE, id_value=self.id_value, url=self.url)
        return self.page

    def scrape(self) -> PageData:
        """subclass should implement this, return PageData object"""
        data = PageData()
        return data

    def get_item(self):
        p = self.get_page()
        if not p:
            raise ValueError(f'page not available for {self.url}')
        model = p.get_preferred_model()
        if not model:
            model = self.DEFAULT_MODEL
        t, v = model.get_best_lookup_id(p.get_all_lookup_ids())
        if t is not None:
            p.item = model.objects.filter(primary_lookup_id_type=t, primary_lookup_id_value=v).first()
        if p.item is None:
            obj = model.copy_metadata(p.metadata)
            obj['primary_lookup_id_type'] = t
            obj['primary_lookup_id_value'] = v
            p.item = model.objects.create(**obj)
        return p.item

    @property
    def ready(self):
        return bool(self.page and self.page.ready)

    def get_page_ready(self, auto_save=True, auto_create=True, auto_link=True):
        """return a page scraped, or scrape if not yet""" 
        if auto_link:
            auto_create = True
        if auto_create:
            auto_save = True
        p = self.get_page()
        pagedata = {}
        if not self.page:
            return None
        if not p.ready:
            pagedata = self.scrape()
            p.update_content(pagedata)
        if not p.ready:
            logger.error(f'unable to get page {self.url} ready')
            return None
        if auto_create and p.item is None:
            self.get_item()
        if auto_save:
            p.save()
            if p.item:
                p.item.merge_data_from_extenal_pages()
                p.item.save()
        if auto_link:
            # todo rewrite this
            p.item.update_linked_items_from_extenal_page(p)
        return p

    def get_dependent_pages_ready(self, urls):
        # set depth = 2 so in a case of douban season can find an IMDB episode then a TMDB Serie
        pass


class SiteList:
    registry = {}

    @classmethod
    def register(cls, target) -> Callable:
        id_type = target.ID_TYPE
        if id_type in cls.registry:
            raise ValueError(f'Site for {id_type} already exists')
        cls.registry[id_type] = target
        return target

    @classmethod
    def get_site_by_id_type(cls, typ: str):
        return cls.registry[typ]() if typ in cls.registry else None

    @classmethod
    def get_site_by_url(cls, url: str):
        cls = next(filter(lambda p: p.validate_url(url), cls.registry.values()), None)
        return cls(url) if cls else None

    @classmethod
    def get_id_by_url(cls, url: str):
        site = cls.get_site_by_url(url)
        return site.url_to_id(url) if site else None
