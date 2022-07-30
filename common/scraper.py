import requests
import functools
import random
import logging
import re
import dateparser
import datetime
import time
import filetype
import dns.resolver
import urllib.parse
from lxml import html
from threading import Thread
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from common.models import SourceSiteEnum
from django.conf import settings
from django.core.exceptions import ValidationError


RE_NUMBERS = re.compile(r"\d+\d*")
RE_WHITESPACES = re.compile(r"\s+")


DEFAULT_REQUEST_HEADERS = {
    'Host': '',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:70.0) Gecko/20100101 Firefox/70.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
    # well, since brotli lib is so bothering, remove `br`
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'DNT': '1',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'no-cache',
}


# luminati account credentials
PORT = 22225


logger = logging.getLogger(__name__)


# register all implemented scraper in form of {host: scraper_class,}
scraper_registry = {}


def get_normalized_url(raw_url):
    url = re.sub(r'//m.douban.com/(\w+)/', r'//\1.douban.com/', raw_url)
    url = re.sub(r'//www.google.com/books/edition/_/([A-Za-z0-9_\-]+)[\?]*', r'//books.google.com/books?id=\1&', url)
    return url


def log_url(func):
    """
    Catch exceptions and log then pass the exceptions.
    First postion argument (except cls/self) of decorated function must be the url.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # log the url and trace stack
            logger.error(f"Scrape Failed URL: {args[1]}\n{e}")
            if settings.DEBUG:
                logger.error("Expections during scraping:", exc_info=e)
            raise e

    return wrapper


def parse_date(raw_str):
    return dateparser.parse(
        raw_str,
        settings={
            "RELATIVE_BASE": datetime.datetime(1900, 1, 1)
        }
    )


class AbstractScraper:
    """
    Scrape entities. The entities means those defined in the models.py file,
    like Book, Movie......
    """

    # subclasses must specify those two variables
    # site means general sites, like amazon/douban etc
    site_name = None
    # host means technically hostname
    host = None
    # corresponding data class
    data_class = None
    # corresponding form class
    form_class = None
    # used to extract effective url
    regex = None
    # scraped raw image
    raw_img = None
    # scraped raw data
    raw_data = {}

    def __init_subclass__(cls, **kwargs):
        # this statement initialize the subclasses
        super().__init_subclass__(**kwargs)
        assert cls.site_name is not None, "class variable `site_name` must be specified"
        assert bool(cls.host), "class variable `host` must be specified"
        assert cls.data_class is not None, "class variable `data_class` must be specified"
        assert cls.form_class is not None, "class variable `form_class` must be specified"
        assert cls.regex is not None, "class variable `regex` must be specified"
        assert isinstance(cls.host, str) or (isinstance(cls.host, list) and isinstance(
            cls.host[0], str)), "`host` must be type str or list"
        assert cls.site_name in SourceSiteEnum, "`site_name` must be one of `SourceSiteEnum` value"
        assert hasattr(cls, 'scrape') and callable(
            cls.scrape), "scaper must have method `.scrape()`"

        # decorate the scrape method
        cls.scrape = classmethod(log_url(cls.scrape))

        # register scraper
        if isinstance(cls.host, list):
            for host in cls.host:
                scraper_registry[host] = cls
        else:
            scraper_registry[cls.host] = cls

    def scrape(self, url):
        """
        Scrape/request model schema specified data from given url and return it.
        Implementations of subclasses to this method would be decorated as class method.
        return (data_dict, image)
        Should set the `raw_data` and the `raw_img`
        """
        raise NotImplementedError("Subclass should implement this method")

    @classmethod
    def get_effective_url(cls, raw_url):
        """
        The return value should be identical with that saved in DB as `source_url`
        """
        url = cls.regex.findall(raw_url.replace('http:', 'https:'))  # force all http to be https
        if not url:
            raise ValueError(f"not valid url: {raw_url}")
        return url[0]

    @classmethod
    def download_page(cls, url, headers):
        url = cls.get_effective_url(url)

        if settings.LUMINATI_USERNAME is None:
            proxies = None
            if settings.SCRAPESTACK_KEY is not None:
                url = f'http://api.scrapestack.com/scrape?access_key={settings.SCRAPESTACK_KEY}&url={url}'
        else:
            session_id = random.random()
            proxy_url = ('http://%s-country-cn-session-%s:%s@zproxy.lum-superproxy.io:%d' %
                         (settings.LUMINATI_USERNAME, session_id, settings.LUMINATI_PASSWORD, PORT))
            proxies = {
                'http': proxy_url,
                'https': proxy_url,
            }

        r = requests.get(url, proxies=proxies,
                         headers=headers, timeout=settings.SCRAPING_TIMEOUT)

        if r.status_code != 200:
            raise RuntimeError(f"download page failed, status code {r.status_code}")
        # with open('temp.html', 'w', encoding='utf-8') as fp:
        #     fp.write(r.content.decode('utf-8'))
        return html.fromstring(r.content.decode('utf-8'))

    @classmethod
    def download_image(cls, url, item_url=None):
        if url is None:
            return None, None
        raw_img = None
        session_id = random.random()
        proxy_url = ('http://%s-country-cn-session-%s:%s@zproxy.lum-superproxy.io:%d' %
                     (settings.LUMINATI_USERNAME, session_id, settings.LUMINATI_PASSWORD, PORT))
        proxies = {
            'http': proxy_url,
            'https': proxy_url,
        }
        if settings.LUMINATI_USERNAME is None:
            proxies = None
        if url:
            img_response = requests.get(
                url,
                headers={
                    'accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                    'accept-encoding': 'gzip, deflate',
                    'accept-language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,fr-FR;q=0.6,fr;q=0.5,zh-TW;q=0.4',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36 Edg/81.0.416.72',
                    'cache-control': 'no-cache',
                    'dnt': '1',
                },
                proxies=proxies,
                timeout=settings.SCRAPING_TIMEOUT,
            )
            if img_response.status_code == 200:
                raw_img = img_response.content
                content_type = img_response.headers.get('Content-Type')
                ext = filetype.get_type(mime=content_type.partition(';')[0].strip()).extension
            else:
                ext = None
        return raw_img, ext

    @classmethod
    def save(cls, request_user):
        entity_cover = {
            'cover': SimpleUploadedFile('temp.' + cls.img_ext, cls.raw_img)
        } if cls.img_ext is not None else None
        form = cls.form_class(cls.raw_data, entity_cover)
        if form.is_valid():
            form.instance.last_editor = request_user
            form.save()
            cls.instance = form.instance
        else:
            logger.error(str(form.errors))
            raise ValidationError("Form invalid.")
        return form


from common.scrapers.bandcamp import BandcampAlbumScraper
from common.scrapers.goodreads import GoodreadsScraper
from common.scrapers.google import GoogleBooksScraper
from common.scrapers.tmdb import TmdbMovieScraper
from common.scrapers.steam import SteamGameScraper
from common.scrapers.imdb import ImdbMovieScraper
from common.scrapers.spotify import SpotifyAlbumScraper, SpotifyTrackScraper
from common.scrapers.douban import DoubanAlbumScraper, DoubanBookScraper, DoubanGameScraper, DoubanMovieScraper
from common.scrapers.bangumi import BangumiScraper


def get_scraper_by_url(url):
    parsed_url = urllib.parse.urlparse(url)
    hostname = parsed_url.netloc
    for host in scraper_registry:
        if host in url:
            return scraper_registry[host]
    # TODO move this logic to scraper class
    try:
        answers = dns.resolver.query(hostname, 'CNAME')
        for rdata in answers:
            if str(rdata.target) == 'dom.bandcamp.com.':
                return BandcampAlbumScraper
    except Exception as e:
        pass
    try:
        answers = dns.resolver.query(hostname, 'A')
        for rdata in answers:
            if str(rdata.address) == '35.241.62.186':
                return BandcampAlbumScraper
    except Exception as e:
        pass
    return None
