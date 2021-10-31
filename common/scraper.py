import requests
import functools
import random
import logging
import re
import dateparser
import datetime
import time
import filetype
from lxml import html
from threading import Thread
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from common.models import SourceSiteEnum
from movies.models import Movie, MovieGenreEnum
from movies.forms import MovieForm
from books.models import Book
from books.forms import BookForm
from music.models import Album, Song
from music.forms import AlbumForm, SongForm
from games.models import Game
from games.forms import GameForm
from django.conf import settings
from PIL import Image
from io import BytesIO


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

# in seconds
TIMEOUT = 60

# luminati account credentials
PORT = 22225

logger = logging.getLogger(__name__)


# register all implemented scraper in form of {host: scraper_class,}
scraper_registry = {}


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
            raise ValueError("not valid url")
        return url[0]

    @classmethod
    def download_page(cls, url, headers):
        url = cls.get_effective_url(url)

        session_id = random.random()
        proxy_url = ('http://%s-country-cn-session-%s:%s@zproxy.lum-superproxy.io:%d' %
                     (settings.LUMINATI_USERNAME, session_id, settings.LUMINATI_PASSWORD, PORT))
        proxies = {
            'http': proxy_url,
            'https': proxy_url,
        }
        if settings.LUMINATI_USERNAME is None:
            proxies = None
        r = requests.get(url, proxies=proxies,
                         headers=headers, timeout=TIMEOUT)

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
                timeout=TIMEOUT,
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


class DoubanScrapperMixin:
    @classmethod
    def download_page(cls, url, headers):
        url = cls.get_effective_url(url)
        r = None
        error = 'DoubanScrapper: error occured when downloading ' + url
        content = None
        last_error = None

        def get(url, timeout):
            nonlocal r
            # print('Douban GET ' + url)
            try:
                r = requests.get(url, timeout=timeout)
            except Exception as e:
                r = requests.Response()
                r.status_code = f"Exception when GET {url} {e}" + url
            # print('Douban CODE ' + str(r.status_code))
            return r

        def check_content():
            nonlocal r, error, content, last_error
            content = None
            last_error = None
            if r.status_code == 200:
                content = r.content.decode('utf-8')
                if content.find('关于豆瓣') == -1:
                    content = None
                    last_error = 'network'
                    error = error + 'Content not authentic'  # response is garbage
                elif re.search('不存在[^<]+</title>', content, re.MULTILINE):
                    content = None
                    last_error = 'censorship'
                    error = error + 'Not found or hidden by Douban'
            else:
                last_error = 'network'
                error = error + str(r.status_code)

        def fix_wayback_links():
            nonlocal content
            # fix links
            content = re.sub(r'href="http[^"]+http', r'href="http', content)
            # https://img9.doubanio.com/view/subject/{l|m|s}/public/s1234.jpg
            content = re.sub(r'src="[^"]+/(s\d+\.\w+)"',
                             r'src="https://img9.doubanio.com/view/subject/m/public/\1"', content)
            # https://img9.doubanio.com/view/photo/s_ratio_poster/public/p2681329386.jpg
            # https://img9.doubanio.com/view/photo/{l|m|s}/public/p1234.webp
            content = re.sub(r'src="[^"]+/(p\d+\.\w+)"',
                             r'src="https://img9.doubanio.com/view/photo/m/public/\1"', content)

        # Wayback Machine: get latest available
        def wayback():
            nonlocal r, error, content
            error = error + '\nWayback: '
            get('http://archive.org/wayback/available?url=' + url, 10)
            if r.status_code == 200:
                w = r.json()
                if w['archived_snapshots'] and w['archived_snapshots']['closest']:
                    get(w['archived_snapshots']['closest']['url'], 10)
                    check_content()
                    if content is not None:
                        fix_wayback_links()
                else:
                    error = error + 'No snapshot available'
            else:
                error = error + str(r.status_code)

        # Wayback Machine: guess via CDX API
        def wayback_cdx():
            nonlocal r, error, content
            error = error + '\nWayback: '
            get('http://web.archive.org/cdx/search/cdx?url=' + url, 10)
            if r.status_code == 200:
                dates = re.findall(r'[^\s]+\s+(\d+)\s+[^\s]+\s+[^\s]+\s+\d+\s+[^\s]+\s+\d{5,}',
                                   r.content.decode('utf-8'))
                # assume snapshots whose size >9999 contain real content, use the latest one of them
                if len(dates) > 0:
                    get('http://web.archive.org/web/' + dates[-1] + '/' + url, 10)
                    check_content()
                    if content is not None:
                        fix_wayback_links()
                else:
                    error = error + 'No snapshot available'
            else:
                error = error + str(r.status_code)

        def latest():
            nonlocal r, error, content
            if settings.SCRAPERAPI_KEY is None:
                error = error + '\nDirect: '
                get(url, 30)
            else:
                error = error + '\nScraperAPI: '
                get(f'http://api.scraperapi.com?api_key={settings.SCRAPERAPI_KEY}&url={url}', 30)
            check_content()
            if last_error == 'network' and settings.PROXYCRAWL_KEY is not None:
                error = error + '\nProxyCrawl: '
                get(f'https://api.proxycrawl.com/?token={settings.PROXYCRAWL_KEY}&url={url}', 30)
                check_content()

        latest()
        if content is None:
            wayback_cdx()

        if content is None:
            raise RuntimeError(error)
        # with open('/tmp/temp.html', 'w', encoding='utf-8') as fp:
        #     fp.write(content)
        return html.fromstring(content)

    @classmethod
    def download_image(cls, url, item_url=None):
        raw_img = None
        ext = None

        dl_url = url
        if settings.SCRAPERAPI_KEY is not None:
            dl_url = f'http://api.scraperapi.com?api_key={settings.SCRAPERAPI_KEY}&url={url}'

        try:
            img_response = requests.get(dl_url, timeout=30)
            if img_response.status_code == 200:
                raw_img = img_response.content
                img = Image.open(BytesIO(raw_img))
                img.load()  # corrupted image will trigger exception
                content_type = img_response.headers.get('Content-Type')
                ext = filetype.get_type(mime=content_type.partition(';')[0].strip()).extension
            else:
                logger.error(f"Douban: download image failed {img_response.status_code} {dl_url} {item_url}")
                # raise RuntimeError(f"Douban: download image failed {img_response.status_code} {dl_url}")
        except Exception as e:
            raw_img = None
            ext = None
            logger.error(f"Douban: download image failed {e} {dl_url} {item_url}")
        if raw_img is None and settings.PROXYCRAWL_KEY is not None:
            try:
                dl_url = f'https://api.proxycrawl.com/?token={settings.PROXYCRAWL_KEY}&url={url}'
                img_response = requests.get(dl_url, timeout=30)
                if img_response.status_code == 200:
                    raw_img = img_response.content
                    img = Image.open(BytesIO(raw_img))
                    img.load()  # corrupted image will trigger exception
                    content_type = img_response.headers.get('Content-Type')
                    ext = filetype.get_type(mime=content_type.partition(';')[0].strip()).extension
                else:
                    logger.error(f"Douban: download image failed {img_response.status_code} {dl_url} {item_url}")
            except Exception as e:
                raw_img = None
                ext = None
                logger.error(f"Douban: download image failed {e} {dl_url} {item_url}")
        return raw_img, ext


class DoubanBookScraper(DoubanScrapperMixin, AbstractScraper):
    site_name = SourceSiteEnum.DOUBAN.value
    host = "book.douban.com"
    data_class = Book
    form_class = BookForm

    regex = re.compile(r"https://book\.douban\.com/subject/\d+/{0,1}")

    def scrape(self, url):
        headers = DEFAULT_REQUEST_HEADERS.copy()
        headers['Host'] = self.host
        content = self.download_page(url, headers)

        # parsing starts here
        try:
            title = content.xpath("/html/body//h1/span/text()")[0].strip()
        except IndexError:
            raise ValueError("given url contains no book info")

        subtitle_elem = content.xpath(
            "//div[@id='info']//span[text()='副标题:']/following::text()")
        subtitle = subtitle_elem[0].strip() if subtitle_elem else None

        orig_title_elem = content.xpath(
            "//div[@id='info']//span[text()='原作名:']/following::text()")
        orig_title = orig_title_elem[0].strip() if orig_title_elem else None

        language_elem = content.xpath(
            "//div[@id='info']//span[text()='语言:']/following::text()")
        language = language_elem[0].strip() if language_elem else None

        pub_house_elem = content.xpath(
            "//div[@id='info']//span[text()='出版社:']/following::text()")
        pub_house = pub_house_elem[0].strip() if pub_house_elem else None

        pub_date_elem = content.xpath(
            "//div[@id='info']//span[text()='出版年:']/following::text()")
        pub_date = pub_date_elem[0].strip() if pub_date_elem else ''
        year_month_day = RE_NUMBERS.findall(pub_date)
        if len(year_month_day) in (2, 3):
            pub_year = int(year_month_day[0])
            pub_month = int(year_month_day[1])
        elif len(year_month_day) == 1:
            pub_year = int(year_month_day[0])
            pub_month = None
        else:
            pub_year = None
            pub_month = None
        if pub_year and pub_month and pub_year < pub_month:
            pub_year, pub_month = pub_month, pub_year
        pub_year = None if pub_year is not None and not pub_year in range(
            0, 3000) else pub_year
        pub_month = None if pub_month is not None and not pub_month in range(
            1, 12) else pub_month

        binding_elem = content.xpath(
            "//div[@id='info']//span[text()='装帧:']/following::text()")
        binding = binding_elem[0].strip() if binding_elem else None

        price_elem = content.xpath(
            "//div[@id='info']//span[text()='定价:']/following::text()")
        price = price_elem[0].strip() if price_elem else None

        pages_elem = content.xpath(
            "//div[@id='info']//span[text()='页数:']/following::text()")
        pages = pages_elem[0].strip() if pages_elem else None
        if pages is not None:
            pages = int(RE_NUMBERS.findall(pages)[
                        0]) if RE_NUMBERS.findall(pages) else None

        isbn_elem = content.xpath(
            "//div[@id='info']//span[text()='ISBN:']/following::text()")
        isbn = isbn_elem[0].strip() if isbn_elem else None

        brief_elem = content.xpath(
            "//h2/span[text()='内容简介']/../following-sibling::div[1]//div[@class='intro'][not(ancestor::span[@class='short'])]/p/text()")
        brief = '\n'.join(p.strip()
                          for p in brief_elem) if brief_elem else None

        contents = None
        try:
            contents_elem = content.xpath(
                "//h2/span[text()='目录']/../following-sibling::div[1]")[0]
            # if next the id of next sibling contains `dir`, that would be the full contents
            if "dir" in contents_elem.getnext().xpath("@id")[0]:
                contents_elem = contents_elem.getnext()
                contents = '\n'.join(p.strip() for p in contents_elem.xpath(
                    "text()")[:-2]) if contents_elem else None
            else:
                contents = '\n'.join(p.strip() for p in contents_elem.xpath(
                    "text()")) if contents_elem else None
        except Exception:
            pass

        img_url_elem = content.xpath("//*[@id='mainpic']/a/img/@src")
        img_url = img_url_elem[0].strip() if img_url_elem else None
        raw_img, ext = self.download_image(img_url, url)

        # there are two html formats for authors and translators
        authors_elem = content.xpath("""//div[@id='info']//span[text()='作者:']/following-sibling::br[1]/
            preceding-sibling::a[preceding-sibling::span[text()='作者:']]/text()""")
        if not authors_elem:
            authors_elem = content.xpath(
                """//div[@id='info']//span[text()=' 作者']/following-sibling::a/text()""")
        if authors_elem:
            authors = []
            for author in authors_elem:
                authors.append(RE_WHITESPACES.sub(' ', author.strip()))
        else:
            authors = None

        translators_elem = content.xpath("""//div[@id='info']//span[text()='译者:']/following-sibling::br[1]/
            preceding-sibling::a[preceding-sibling::span[text()='译者:']]/text()""")
        if not translators_elem:
            translators_elem = content.xpath(
                """//div[@id='info']//span[text()=' 译者']/following-sibling::a/text()""")
        if translators_elem:
            translators = []
            for translator in translators_elem:
                translators.append(RE_WHITESPACES.sub(' ', translator.strip()))
        else:
            translators = None

        other = {}
        cncode_elem = content.xpath(
            "//div[@id='info']//span[text()='统一书号:']/following::text()")
        if cncode_elem:
            other['统一书号'] = cncode_elem[0].strip()
        series_elem = content.xpath(
            "//div[@id='info']//span[text()='丛书:']/following-sibling::a[1]/text()")
        if series_elem:
            other['丛书'] = series_elem[0].strip()
        imprint_elem = content.xpath(
            "//div[@id='info']//span[text()='出品方:']/following-sibling::a[1]/text()")
        if imprint_elem:
            other['出品方'] = imprint_elem[0].strip()

        data = {
            'title': title,
            'subtitle': subtitle,
            'orig_title': orig_title,
            'author': authors,
            'translator': translators,
            'language': language,
            'pub_house': pub_house,
            'pub_year': pub_year,
            'pub_month': pub_month,
            'binding': binding,
            'price': price,
            'pages': pages,
            'isbn': isbn,
            'brief': brief,
            'contents': contents,
            'other_info': other,
            'source_site': self.site_name,
            'source_url': self.get_effective_url(url),
        }
        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img


class DoubanMovieScraper(DoubanScrapperMixin, AbstractScraper):
    site_name = SourceSiteEnum.DOUBAN.value
    host = 'movie.douban.com'
    data_class = Movie
    form_class = MovieForm

    regex = re.compile(r"https://movie\.douban\.com/subject/\d+/{0,1}")

    def scrape(self, url):
        headers = DEFAULT_REQUEST_HEADERS.copy()
        headers['Host'] = self.host
        content = self.download_page(url, headers)

        # parsing starts here
        try:
            raw_title = content.xpath(
                "//span[@property='v:itemreviewed']/text()")[0].strip()
        except IndexError:
            raise ValueError("given url contains no movie info")

        orig_title = content.xpath(
            "//img[@rel='v:image']/@alt")[0].strip()
        title = raw_title.split(orig_title)[0].strip()
        # if has no chinese title
        if title == '':
            title = orig_title

        if title == orig_title:
            orig_title = None

        # there are two html formats for authors and translators
        other_title_elem = content.xpath(
            "//div[@id='info']//span[text()='又名:']/following-sibling::text()[1]")
        other_title = other_title_elem[0].strip().split(
            ' / ') if other_title_elem else None

        imdb_elem = content.xpath(
            "//div[@id='info']//span[text()='IMDb链接:']/following-sibling::a[1]/text()")
        if not imdb_elem:
            imdb_elem = content.xpath(
                "//div[@id='info']//span[text()='IMDb:']/following-sibling::text()[1]")
        imdb_code = imdb_elem[0].strip() if imdb_elem else None

        director_elem = content.xpath(
            "//div[@id='info']//span[text()='导演']/following-sibling::span[1]/a/text()")
        director = director_elem if director_elem else None

        playwright_elem = content.xpath(
            "//div[@id='info']//span[text()='编剧']/following-sibling::span[1]/a/text()")
        playwright = playwright_elem if playwright_elem else None

        actor_elem = content.xpath(
            "//div[@id='info']//span[text()='主演']/following-sibling::span[1]/a/text()")
        actor = actor_elem if actor_elem else None

        # construct genre translator
        genre_translator = {}
        attrs = [attr for attr in dir(MovieGenreEnum) if not '__' in attr]
        for attr in attrs:
            genre_translator[getattr(MovieGenreEnum, attr).label] = getattr(
                MovieGenreEnum, attr).value

        genre_elem = content.xpath("//span[@property='v:genre']/text()")
        if genre_elem:
            genre = []
            for g in genre_elem:
                genre.append(genre_translator[g])
        else:
            genre = None

        showtime_elem = content.xpath(
            "//span[@property='v:initialReleaseDate']/text()")
        if showtime_elem:
            showtime = []
            for st in showtime_elem:
                parts = st.split('(')
                if len(parts) == 1:
                    time = st.split('(')[0]
                    region = ''
                else:
                    time = st.split('(')[0]
                    region = st.split('(')[1][0:-1]
                showtime.append({time: region})
        else:
            showtime = None

        site_elem = content.xpath(
            "//div[@id='info']//span[text()='官方网站:']/following-sibling::a[1]/@href")
        site = site_elem[0].strip() if site_elem else None

        area_elem = content.xpath(
            "//div[@id='info']//span[text()='制片国家/地区:']/following-sibling::text()[1]")
        if area_elem:
            area = [a.strip() for a in area_elem[0].split(' / ')]
        else:
            area = None

        language_elem = content.xpath(
            "//div[@id='info']//span[text()='语言:']/following-sibling::text()[1]")
        if language_elem:
            language = [a.strip() for a in language_elem[0].split(' / ')]
        else:
            language = None

        year_elem = content.xpath("//span[@class='year']/text()")
        year = int(year_elem[0][1:-1]) if year_elem else None

        duration_elem = content.xpath("//span[@property='v:runtime']/text()")
        other_duration_elem = content.xpath(
            "//span[@property='v:runtime']/following-sibling::text()[1]")
        if duration_elem:
            duration = duration_elem[0].strip()
            if other_duration_elem:
                duration += other_duration_elem[0].rstrip()
        else:
            duration = None

        season_elem = content.xpath(

            "//*[@id='season']/option[@selected='selected']/text()")
        if not season_elem:
            season_elem = content.xpath(
                "//div[@id='info']//span[text()='季数:']/following-sibling::text()[1]")
            season = int(season_elem[0].strip()) if season_elem else None
        else:
            season = int(season_elem[0].strip())

        episodes_elem = content.xpath(
            "//div[@id='info']//span[text()='集数:']/following-sibling::text()[1]")
        episodes = int(episodes_elem[0].strip()) if episodes_elem else None

        single_episode_length_elem = content.xpath(
            "//div[@id='info']//span[text()='单集片长:']/following-sibling::text()[1]")
        single_episode_length = single_episode_length_elem[0].strip(
        ) if single_episode_length_elem else None

        # if has field `episodes` not none then must be series
        is_series = True if episodes else False

        brief_elem = content.xpath("//span[@class='all hidden']")
        if not brief_elem:
            brief_elem = content.xpath("//span[@property='v:summary']")
        brief = '\n'.join([e.strip() for e in brief_elem[0].xpath(
            './text()')]) if brief_elem else None

        img_url_elem = content.xpath("//img[@rel='v:image']/@src")
        img_url = img_url_elem[0].strip() if img_url_elem else None
        raw_img, ext = self.download_image(img_url, url)

        data = {
            'title': title,
            'orig_title': orig_title,
            'other_title': other_title,
            'imdb_code': imdb_code,
            'director': director,
            'playwright': playwright,
            'actor': actor,
            'genre': genre,
            'showtime': showtime,
            'site': site,
            'area': area,
            'language': language,
            'year': year,
            'duration': duration,
            'season': season,
            'episodes': episodes,
            'single_episode_length': single_episode_length,
            'brief': brief,
            'is_series': is_series,
            'source_site': self.site_name,
            'source_url': self.get_effective_url(url),
        }
        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img


class DoubanAlbumScraper(DoubanScrapperMixin, AbstractScraper):
    site_name = SourceSiteEnum.DOUBAN.value
    host = 'music.douban.com'
    data_class = Album
    form_class = AlbumForm

    regex = re.compile(r"https://music\.douban\.com/subject/\d+/{0,1}")

    def scrape(self, url):
        headers = DEFAULT_REQUEST_HEADERS.copy()
        headers['Host'] = self.host
        content = self.download_page(url, headers)

        # parsing starts here
        try:
            title = content.xpath("//h1/span/text()")[0].strip()
        except IndexError:
            raise ValueError("given url contains no album info")
        if not title:
            raise ValueError("given url contains no album info")


        artists_elem = content.xpath("""//div[@id='info']/span/span[@class='pl']/a/text()""")
        artist = None if not artists_elem else artists_elem

        genre_elem = content.xpath(
            "//div[@id='info']//span[text()='流派:']/following::text()[1]")
        genre = genre_elem[0].strip() if genre_elem else None

        date_elem = content.xpath(
            "//div[@id='info']//span[text()='发行时间:']/following::text()[1]")
        release_date = parse_date(date_elem[0].strip()) if date_elem else None

        company_elem = content.xpath(
            "//div[@id='info']//span[text()='出版者:']/following::text()[1]")
        company = company_elem[0].strip() if company_elem else None

        track_list_elem = content.xpath(
            "//div[@class='track-list']/div[@class='indent']/div/text()"
        )
        if track_list_elem:
            track_list = '\n'.join([track.strip() for track in track_list_elem])
        else:
            track_list = None

        brief_elem = content.xpath("//span[@class='all hidden']")
        if not brief_elem:
            brief_elem = content.xpath("//span[@property='v:summary']")
        brief = '\n'.join([e.strip() for e in brief_elem[0].xpath(
            './text()')]) if brief_elem else None

        other_info = {}
        other_elem = content.xpath(
            "//div[@id='info']//span[text()='又名:']/following-sibling::text()[1]")
        if other_elem:
            other_info['又名'] = other_elem[0].strip()
        other_elem = content.xpath(
            "//div[@id='info']//span[text()='专辑类型:']/following-sibling::text()[1]")
        if other_elem:
            other_info['专辑类型'] = other_elem[0].strip()
        other_elem = content.xpath(
            "//div[@id='info']//span[text()='介质:']/following-sibling::text()[1]")
        if other_elem:
            other_info['介质'] = other_elem[0].strip()
        other_elem = content.xpath(
            "//div[@id='info']//span[text()='ISRC:']/following-sibling::text()[1]")
        if other_elem:
            other_info['ISRC'] = other_elem[0].strip()
        other_elem = content.xpath(
            "//div[@id='info']//span[text()='条形码:']/following-sibling::text()[1]")
        if other_elem:
            other_info['条形码'] = other_elem[0].strip()
        other_elem = content.xpath(
            "//div[@id='info']//span[text()='碟片数:']/following-sibling::text()[1]")
        if other_elem:
            other_info['碟片数'] = other_elem[0].strip()

        img_url_elem = content.xpath("//div[@id='mainpic']//img/@src")
        img_url = img_url_elem[0].strip() if img_url_elem else None
        raw_img, ext = self.download_image(img_url, url)

        data = {
            'title': title,
            'artist': artist,
            'genre': genre,
            'release_date': release_date,
            'duration': None,
            'company': company,
            'track_list': track_list,
            'brief': brief,
            'other_info': other_info,
            'source_site': self.site_name,
            'source_url': self.get_effective_url(url),
        }
        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img


spotify_token = None
spotify_token_expire_time = time.time()

class SpotifyTrackScraper(AbstractScraper):
    site_name = SourceSiteEnum.SPOTIFY.value
    host = 'https://open.spotify.com/track/'
    data_class = Song
    form_class = SongForm

    regex = re.compile(r"(?<=https://open\.spotify\.com/track/)[a-zA-Z0-9]+")

    def scrape(self, url):
        """
        Request from API, not really scraping
        """
        global spotify_token, spotify_token_expire_time

        if spotify_token is None or is_spotify_token_expired():
            invoke_spotify_token()
        effective_url = self.get_effective_url(url)
        if effective_url is None:
            raise ValueError("not valid url")

        api_url = self.get_api_url(effective_url)
        headers = {
            'Authorization': f"Bearer {spotify_token}"
        }
        r = requests.get(api_url, headers=headers)
        res_data = r.json()

        artist = []
        for artist_dict in res_data['artists']:
            artist.append(artist_dict['name'])
        if not artist:
            artist = None

        title = res_data['name']

        release_date = parse_date(res_data['album']['release_date'])

        duration = res_data['duration_ms']

        if res_data['external_ids'].get('isrc'):
            isrc = res_data['external_ids']['isrc']
        else:
            isrc = None

        raw_img, ext = self.download_image(res_data['album']['images'][0]['url'], url)

        data = {
            'title': title,
            'artist': artist,
            'genre': None,
            'release_date': release_date,
            'duration': duration,
            'isrc': isrc,
            'album': None,
            'brief': None,
            'other_info': None,
            'source_site': self.site_name,
            'source_url': effective_url,
        }
        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img

    @classmethod
    def get_effective_url(cls, raw_url):
        code = cls.regex.findall(raw_url)
        if code:
            return f"https://open.spotify.com/track/{code[0]}"
        else:
            return None

    @classmethod
    def get_api_url(cls, url):
        return "https://api.spotify.com/v1/tracks/" + cls.regex.findall(url)[0]


class SpotifyAlbumScraper(AbstractScraper):
    site_name = SourceSiteEnum.SPOTIFY.value
    # API URL
    host = 'https://open.spotify.com/album/'
    data_class = Album
    form_class = AlbumForm

    regex = re.compile(r"(?<=https://open\.spotify\.com/album/)[a-zA-Z0-9]+")

    def scrape(self, url):
        """
        Request from API, not really scraping
        """
        global spotify_token, spotify_token_expire_time

        if spotify_token is None or is_spotify_token_expired():
            invoke_spotify_token()
        effective_url = self.get_effective_url(url)
        if effective_url is None:
            raise ValueError("not valid url")

        api_url = self.get_api_url(effective_url)
        headers = {
            'Authorization': f"Bearer {spotify_token}"
        }
        r = requests.get(api_url, headers=headers)
        res_data = r.json()

        artist = []
        for artist_dict in res_data['artists']:
            artist.append(artist_dict['name'])

        title = res_data['name']

        genre = ', '.join(res_data['genres'])

        company = []
        for com in res_data['copyrights']:
            company.append(com['text'])

        duration = 0
        track_list = []
        track_urls = []
        for track in res_data['tracks']['items']:
            track_urls.append(track['external_urls']['spotify'])
            duration += track['duration_ms']
            if res_data['tracks']['items'][-1]['disc_number'] > 1:
                # more than one disc
                track_list.append(str(
                    track['disc_number']) + '-' + str(track['track_number']) + '. ' + track['name'])
            else:
                track_list.append(str(track['track_number']) + '. ' + track['name'])
        track_list = '\n'.join(track_list)

        release_date = parse_date(res_data['release_date'])

        other_info = {}
        if res_data['external_ids'].get('upc'):
            # bar code
            other_info['UPC'] = res_data['external_ids']['upc']

        raw_img, ext = self.download_image(res_data['images'][0]['url'], url)

        data = {
            'title': title,
            'artist': artist,
            'genre': genre,
            'track_list': track_list,
            'release_date': release_date,
            'duration': duration,
            'company': company,
            'brief': None,
            'other_info': other_info,
            'source_site': self.site_name,
            'source_url': effective_url,
        }

        # set tracks_data, used for adding tracks
        self.track_urls = track_urls

        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img

    @classmethod
    def get_effective_url(cls, raw_url):
        code = cls.regex.findall(raw_url)
        if code:
            return f"https://open.spotify.com/album/{code[0]}"
        else:
            return None

    @classmethod
    def save(cls, request_user):
        form = super().save(request_user)
        task = Thread(
            target=cls.add_tracks,
            args=(form.instance, request_user),
            daemon=True
        )
        task.start()
        return form

    @classmethod
    def get_api_url(cls, url):
        return "https://api.spotify.com/v1/albums/" + cls.regex.findall(url)[0]

    @classmethod
    def add_tracks(cls, album: Album, request_user):
        to_be_updated_tracks = []
        for track_url in cls.track_urls:
            track = cls.get_track_or_none(track_url)
            # seems lik if fire too many requests at the same time
            # spotify would limit access
            if track is None:
                task = Thread(
                    target=cls.scrape_and_save_track,
                    args=(track_url, album, request_user),
                    daemon=True
                )
                task.start()
                task.join()
            else:
                to_be_updated_tracks.append(track)
        cls.bulk_update_track_album(to_be_updated_tracks, album, request_user)

    @classmethod
    def get_track_or_none(cls, track_url: str):
        try:
            instance = Song.objects.get(source_url=track_url)
            return instance
        except ObjectDoesNotExist:
            return None

    @classmethod
    def scrape_and_save_track(cls, url: str, album: Album, request_user):
        data, img = SpotifyTrackScraper.scrape(url)
        SpotifyTrackScraper.raw_data['album'] = album
        SpotifyTrackScraper.save(request_user)

    @classmethod
    def bulk_update_track_album(cls, tracks, album, request_user):
        for track in tracks:
            track.last_editor = request_user
            track.edited_time = timezone.now()
            track.album = album
        Song.objects.bulk_update(tracks, [
            'last_editor',
            'edited_time',
            'album'
        ])


def get_spotify_token():
    global spotify_token, spotify_token_expire_time
    if spotify_token is None or is_spotify_token_expired():
        invoke_spotify_token()
    return spotify_token

    
def is_spotify_token_expired():
    global spotify_token_expire_time
    return True if spotify_token_expire_time <= time.time() else False


def invoke_spotify_token():
    global spotify_token, spotify_token_expire_time
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "client_credentials"
        },
        headers={
            "Authorization": f"Basic {settings.SPOTIFY_CREDENTIAL}"
        }
    )
    data = r.json()
    if r.status_code == 401:
        # token expired, try one more time
        # this maybe caused by external operations,
        # for example debugging using a http client
        r = requests.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "client_credentials"
            },
            headers={
                "Authorization": f"Basic {settings.SPOTIFY_CREDENTIAL}"
            }
        )
        data = r.json()
    elif r.status_code != 200:
        raise Exception(f"Request to spotify API fails. Reason: {r.reason}")
    # minus 2 for execution time error
    spotify_token_expire_time = int(data['expires_in']) + time.time() - 2
    spotify_token = data['access_token']


class ImdbMovieScraper(AbstractScraper):
    site_name = SourceSiteEnum.IMDB.value
    host = 'https://www.imdb.com/title/'
    data_class = Movie
    form_class = MovieForm

    regex = re.compile(r"(?<=https://www\.imdb\.com/title/)[a-zA-Z0-9]+")

    def scrape(self, url):

        effective_url = self.get_effective_url(url)
        if effective_url is None:
            raise ValueError("not valid url")

        api_url = self.get_api_url(effective_url)
        r = requests.get(api_url)
        res_data = r.json()

        if not res_data['type'] in ['Movie', 'TVSeries']:
            raise ValueError("not movie/series item")

        if res_data['type'] == 'Movie':
            is_series = False
        elif res_data['type'] == 'TVSeries':
            is_series = True

        title = res_data['title']
        orig_title = res_data['originalTitle']
        imdb_code = self.regex.findall(effective_url)[0]
        director = []
        for direct_dict in res_data['directorList']:
            director.append(direct_dict['name'])
        playwright = []
        for writer_dict in res_data['writerList']:
            playwright.append(writer_dict['name'])
        actor = []
        for actor_dict in res_data['actorList']:
            actor.append(actor_dict['name'])
        genre = res_data['genres'].split(', ')
        area = res_data['countries'].split(', ')
        language = res_data['languages'].split(', ')
        year = int(res_data['year'])
        duration = res_data['runtimeStr']
        brief = res_data['plotLocal'] if res_data['plotLocal'] else res_data['plot']
        if res_data['releaseDate']:
            showtime = [{res_data['releaseDate']: "发布日期"}]
        else:
            showtime = None

        other_info = {}
        if res_data['contentRating']:
            other_info['分级'] = res_data['contentRating']
        if res_data['imDbRating']:
            other_info['IMDb评分'] = res_data['imDbRating']
        if res_data['metacriticRating']:
            other_info['Metacritic评分'] = res_data['metacriticRating']
        if res_data['awards']:
            other_info['奖项'] = res_data['awards']

        raw_img, ext = self.download_image(res_data['image'], url)

        data = {
            'title': title,
            'orig_title': orig_title,
            'other_title': None,
            'imdb_code': imdb_code,
            'director': director,
            'playwright': playwright,
            'actor': actor,
            'genre': genre,
            'showtime': showtime,
            'site': None,
            'area': area,
            'language': language,
            'year': year,
            'duration': duration,
            'season': None,
            'episodes': None,
            'single_episode_length': None,
            'brief': brief,
            'is_series': is_series,
            'other_info': other_info,
            'source_site': self.site_name,
            'source_url': effective_url,
        }
        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img

    @classmethod
    def get_effective_url(cls, raw_url):
        code = cls.regex.findall(raw_url)
        if code:
            return f"https://www.imdb.com/title/{code[0]}/"
        else:
            return None

    @classmethod
    def get_api_url(cls, url):
        return f"https://imdb-api.com/zh/API/Title/{settings.IMDB_API_KEY}/{cls.regex.findall(url)[0]}/FullActor,"


class DoubanGameScraper(DoubanScrapperMixin, AbstractScraper):
    site_name = SourceSiteEnum.DOUBAN.value
    host = 'www.douban.com/game/'
    data_class = Game
    form_class = GameForm

    regex = re.compile(r"https://www\.douban\.com/game/\d+/{0,1}")

    def scrape(self, url):
        headers = DEFAULT_REQUEST_HEADERS.copy()
        headers['Host'] = 'www.douban.com'
        content = self.download_page(url, headers)

        try:
            raw_title = content.xpath(
                "//div[@id='content']/h1/text()")[0].strip()
        except IndexError:
            raise ValueError("given url contains no game info")

        title = raw_title

        other_title_elem = content.xpath(
            "//dl[@class='game-attr']//dt[text()='别名:']/following-sibling::dd[1]/text()")
        other_title = other_title_elem[0].strip().split(' / ') if other_title_elem else None

        developer_elem = content.xpath(
            "//dl[@class='game-attr']//dt[text()='开发商:']/following-sibling::dd[1]/text()")
        developer = developer_elem[0].strip().split(' / ') if developer_elem else None

        publisher_elem = content.xpath(
            "//dl[@class='game-attr']//dt[text()='发行商:']/following-sibling::dd[1]/text()")
        publisher = publisher_elem[0].strip().split(' / ') if publisher_elem else None

        platform_elem = content.xpath(
            "//dl[@class='game-attr']//dt[text()='平台:']/following-sibling::dd[1]/a/text()")
        platform = platform_elem if platform_elem else None

        genre_elem = content.xpath(
            "//dl[@class='game-attr']//dt[text()='类型:']/following-sibling::dd[1]/a/text()")
        genre = None
        if genre_elem:
            genre = [g for g in genre_elem if g != '游戏']

        date_elem = content.xpath(
            "//dl[@class='game-attr']//dt[text()='发行日期:']/following-sibling::dd[1]/text()")
        release_date = parse_date(date_elem[0].strip()) if date_elem else None

        brief_elem = content.xpath("//div[@class='mod item-desc']/p/text()")
        brief = '\n'.join(brief_elem) if brief_elem else None

        img_url_elem = content.xpath(
            "//div[@class='item-subject-info']/div[@class='pic']//img/@src")
        img_url = img_url_elem[0].strip() if img_url_elem else None
        raw_img, ext = self.download_image(img_url, url)

        data = {
            'title': title,
            'other_title': other_title,
            'developer': developer,
            'publisher': publisher,
            'release_date': release_date,
            'genre': genre,
            'platform': platform,
            'brief': brief,
            'other_info': None,
            'source_site': self.site_name,
            'source_url': self.get_effective_url(url),
        }

        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img


class SteamGameScraper(AbstractScraper):
    site_name = SourceSiteEnum.STEAM.value
    host = 'store.steampowered.com'
    data_class = Game
    form_class = GameForm

    regex = re.compile(r"https://store\.steampowered\.com/app/\d+/{0,1}")

    def scrape(self, url):
        headers = DEFAULT_REQUEST_HEADERS.copy()
        headers['Host'] = self.host
        headers['Cookie'] = "wants_mature_content=1; birthtime=754700401;"
        content = self.download_page(url, headers)

        title = content.xpath("//div[@class='apphub_AppName']/text()")[0]
        developer = content.xpath("//div[@id='developers_list']/a/text()")
        publisher = content.xpath("//div[@class='glance_ctn']//div[@class='dev_row'][2]//a/text()")
        release_date = parse_date(
            content.xpath(
                "//div[@class='release_date']/div[@class='date']/text()")[0]
        )

        genre = content.xpath(
            "//div[@class='details_block']/b[2]/following-sibling::a/text()")

        platform = ['PC']

        brief = content.xpath(
            "//div[@class='game_description_snippet']/text()")[0].strip()

        img_url = content.xpath(
            "//img[@class='game_header_image_full']/@src"
        )[0].replace("header.jpg", "library_600x900.jpg")
        raw_img, ext = self.download_image(img_url, url)

        # no 600x900 picture
        if raw_img is None:
            img_url = content.xpath("//img[@class='game_header_image_full']/@src")[0]
            raw_img, ext = self.download_image(img_url, url)

        data = {
            'title': title,
            'other_title': None,
            'developer': developer,
            'publisher': publisher,
            'release_date': release_date,
            'genre': genre,
            'platform': platform,
            'brief': brief,
            'other_info': None,
            'source_site': self.site_name,
            'source_url': self.get_effective_url(url),
        }

        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img


def find_entity(source_url):
    """
    for bangumi
    """
    # to be added when new scrape method is implemented
    result = Game.objects.filter(source_url=source_url)
    if result:
        return result[0]
    else:
        raise ObjectDoesNotExist

class BangumiScraper(AbstractScraper):
    site_name = SourceSiteEnum.BANGUMI.value
    host = 'bgm.tv'

    # for interface coherence
    data_class = type("FakeDataClass", (object,), {})()
    data_class.objects = type("FakeObjectsClass", (object,), {})()
    data_class.objects.get = find_entity
    # should be set at scrape_* method
    form_class = ''


    regex = re.compile(r"https{0,1}://bgm\.tv/subject/\d+")

    def scrape(self, url):
        """
        This is the scraping portal
        """
        headers = DEFAULT_REQUEST_HEADERS.copy()
        headers['Host'] = self.host
        content = self.download_page(url, headers)

        # download image
        img_url = 'http:' + content.xpath("//div[@class='infobox']//img[1]/@src")[0]
        raw_img, ext = self.download_image(img_url, url)

        # Test category
        category_code = content.xpath("//div[@id='headerSearch']//option[@selected]/@value")[0]
        handler_map = {
            '1': self.scrape_book,
            '2': self.scrape_movie,
            '3': self.scrape_album,
            '4': self.scrape_game
        }
        data = handler_map[category_code](self, content)
        data['source_url'] = self.get_effective_url(url)

        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img


    def scrape_game(self, content):
        self.data_class = Game
        self.form_class = GameForm

        title_elem = content.xpath("//a[@property='v:itemreviewed']/text()")
        if not title_elem:
            raise ValueError("no game info found on this page")
            title = None
        else:
            title = title_elem[0].strip()

        other_title_elem = content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'别名')]]/text()")
        if not other_title_elem:
            other_title_elem = content.xpath(
                "//ul[@id='infobox']/li[child::span[contains(text(),'别名')]]/a/text()")
        other_title = other_title_elem if other_title_elem else []

        chinese_name_elem = content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'中文')]]/text()")
        if not chinese_name_elem:
            chinese_name_elem = content.xpath(
                "//ul[@id='infobox']/li[child::span[contains(text(),'中文')]]/a/text()")
        if chinese_name_elem:
            chinese_name = chinese_name_elem[0]
            # switch chinese name with original name
            title, chinese_name = chinese_name, title
            # actually the name appended is original
            other_title.append(chinese_name)

        developer_elem = content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'开发')]]/text()")
        if not developer_elem:
            developer_elem = content.xpath(
                "//ul[@id='infobox']/li[child::span[contains(text(),'开发')]]/a/text()")
        developer = developer_elem if developer_elem else None

        publisher_elem = content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'发行:')]]/text()")
        if not publisher_elem:
            publisher_elem = content.xpath(
                "//ul[@id='infobox']/li[child::span[contains(text(),'发行:')]]/a/text()")
        publisher = publisher_elem if publisher_elem else None

        platform_elem = content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'平台')]]/text()")
        if not platform_elem:
            platform_elem = content.xpath(
                "//ul[@id='infobox']/li[child::span[contains(text(),'平台')]]/a/text()")
        platform = platform_elem if platform_elem else None

        genre_elem = content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'类型')]]/text()")
        if not genre_elem:
            genre_elem = content.xpath(
                "//ul[@id='infobox']/li[child::span[contains(text(),'类型')]]/a/text()")
        genre = genre_elem if genre_elem else None

        date_elem = content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'发行日期')]]/text()")
        if not date_elem:
            date_elem = content.xpath(
                "//ul[@id='infobox']/li[child::span[contains(text(),'发行日期')]]/a/text()")
        release_date = parse_date(date_elem[0]) if date_elem else None

        brief = ''.join(content.xpath("//div[@property='v:summary']/text()"))

        other_info = {}
        other_elem = content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'人数')]]/text()")
        if other_elem:
            other_info['游玩人数'] = other_elem[0]
        other_elem = content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'引擎')]]/text()")
        if other_elem:
            other_info['引擎'] = ' '.join(other_elem)
        other_elem = content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'售价')]]/text()")
        if other_elem:
            other_info['售价'] = ' '.join(other_elem)
        other_elem = content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'官方网站')]]/text()")
        if other_elem:
            other_info['网站'] = other_elem[0]
        other_elem = content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'剧本')]]/a/text()") or content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'剧本')]]/text()")
        if other_elem:
            other_info['剧本'] = ' '.join(other_elem)
        other_elem = content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'编剧')]]/a/text()") or content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'编剧')]]/text()")
        if other_elem:
            other_info['编剧'] = ' '.join(other_elem)
        other_elem = content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'音乐')]]/a/text()") or content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'音乐')]]/text()")
        if other_elem:
            other_info['音乐'] = ' '.join(other_elem)
        other_elem = content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'美术')]]/a/text()") or content.xpath(
            "//ul[@id='infobox']/li[child::span[contains(text(),'美术')]]/text()")
        if other_elem:
            other_info['美术'] = ' '.join(other_elem)

        data = {
            'title': title,
            'other_title': None,
            'developer': developer,
            'publisher': publisher,
            'release_date': release_date,
            'genre': genre,
            'platform': platform,
            'brief': brief,
            'other_info': other_info,
            'source_site': self.site_name,
        }

        return data

    def scrape_movie(self, content):
        self.data_class = Movie
        self.form_class = MovieForm
        raise NotImplementedError

    def scrape_book(self, content):
        self.data_class = Book
        self.form_class = BookForm
        raise NotImplementedError

    def scrape_album(self, content):
        self.data_class = Album
        self.form_class = AlbumForm
        raise NotImplementedError


class GoodreadsScraper(AbstractScraper):
    site_name = SourceSiteEnum.GOODREADS.value
    host = "www.goodreads.com"
    data_class = Book
    form_class = BookForm
    regex = re.compile(r"https://www\.goodreads\.com/show/\d+")

    @classmethod
    def get_effective_url(cls, raw_url):
        u = re.match(r"https://www\.goodreads\.com/book/show/\d+", raw_url)
        return u[0] if u else None

    def scrape(self, url, response=None):
        """
        This is the scraping portal
        """
        if response is not None:
            content = html.fromstring(response.content.decode('utf-8'))
        else:
            headers = DEFAULT_REQUEST_HEADERS.copy()
            headers['Host'] = self.host
            content = self.download_page(url, headers)

        try:
            title = content.xpath("//h1[@id='bookTitle']/text()")[0].strip()
        except IndexError:
            raise ValueError("given url contains no book info")

        subtitle = None

        orig_title_elem = content.xpath("//div[@id='bookDataBox']//div[text()='Original Title']/following-sibling::div/text()")
        orig_title = orig_title_elem[0].strip() if orig_title_elem else None

        language_elem = content.xpath('//div[@itemprop="inLanguage"]/text()')
        language = language_elem[0].strip() if language_elem else None

        pub_house_elem = content.xpath("//div[contains(text(), 'Published') and @class='row']/text()")
        try:
            months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
            r = re.compile('.*Published.*(' + '|'.join(months) + ').*(\\d\\d\\d\\d).+by\\s*(.+)\\s*', re.DOTALL)
            pub = r.match(pub_house_elem[0])
            pub_year = pub[2]
            pub_month = months.index(pub[1]) + 1
            pub_house = pub[3].strip()
        except Exception:
            pub_year = None
            pub_month = None
            pub_house = None

        pub_house_elem = content.xpath("//nobr[contains(text(), 'first published')]/text()")
        try:
            pub = re.match(r'.*first published\s+(.+\d\d\d\d).*', pub_house_elem[0], re.DOTALL)
            first_pub = pub[1]
        except Exception:
            first_pub = None

        binding_elem = content.xpath('//span[@itemprop="bookFormat"]/text()')
        binding = binding_elem[0].strip() if binding_elem else None

        pages_elem = content.xpath('//span[@itemprop="numberOfPages"]/text()')
        pages = pages_elem[0].strip() if pages_elem else None
        if pages is not None:
            pages = int(RE_NUMBERS.findall(pages)[
                        0]) if RE_NUMBERS.findall(pages) else None

        isbn_elem = content.xpath('//span[@itemprop="isbn"]/text()')
        if not isbn_elem:
            isbn_elem = content.xpath('//div[@itemprop="isbn"]/text()')  # this is likely ASIN
        isbn = isbn_elem[0].strip() if isbn_elem else None

        brief_elem = content.xpath('//div[@id="description"]/span[@style="display:none"]/text()')
        if brief_elem:
            brief = '\n'.join(p.strip() for p in brief_elem)
        else:
            brief_elem = content.xpath('//div[@id="description"]/span/text()')
            brief = '\n'.join(p.strip() for p in brief_elem) if brief_elem else None

        genre = content.xpath('//div[@class="bigBoxBody"]/div/div/div/a/text()')
        genre = genre[0] if genre else None
        book_title = re.sub('\n', '', content.xpath('//h1[@id="bookTitle"]/text()')[0]).strip()
        author = content.xpath('//a[@class="authorName"]/span/text()')[0]
        contents = None

        img_url_elem = content.xpath("//img[@id='coverImage']/@src")
        img_url = img_url_elem[0].strip() if img_url_elem else None
        raw_img, ext = self.download_image(img_url, url)

        authors_elem = content.xpath("//a[@class='authorName'][not(../span[@class='authorName greyText smallText role'])]/span/text()")
        if authors_elem:
            authors = []
            for author in authors_elem:
                authors.append(RE_WHITESPACES.sub(' ', author.strip()))
        else:
            authors = None

        translators = None
        authors_elem = content.xpath("//a[@class='authorName'][../span/text()='(Translator)']/span/text()")
        if authors_elem:
            translators = []
            for translator in authors_elem:
                translators.append(RE_WHITESPACES.sub(' ', translator.strip()))
        else:
            translators = None

        other = {}
        if first_pub:
            other['首版时间'] = first_pub
        if genre:
            other['分类'] = genre
        series_elem = content.xpath("//h2[@id='bookSeries']/a/text()")
        if series_elem:
            other['丛书'] = re.sub(r'\(\s*(.+[^\s])\s*#.*\)', '\\1', series_elem[0].strip())

        data = {
            'title': title,
            'subtitle': subtitle,
            'orig_title': orig_title,
            'author': authors,
            'translator': translators,
            'language': language,
            'pub_house': pub_house,
            'pub_year': pub_year,
            'pub_month': pub_month,
            'binding': binding,
            'pages': pages,
            'isbn': isbn,
            'brief': brief,
            'contents': contents,
            'other_info': other,
            'cover_url': img_url,
            'source_site': self.site_name,
            'source_url': self.get_effective_url(url),
        }
        data['source_url'] = self.get_effective_url(url)

        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img

class TmdbMovieScraper(AbstractScraper):
    site_name = SourceSiteEnum.TMDB.value
    host = 'https://www.themoviedb.org/'
    data_class = Movie
    form_class = MovieForm
    regex = re.compile(r"https://www\.themoviedb\.org/(movie|tv)/([a-zA-Z0-9]+)")
    # http://api.themoviedb.org/3/genre/movie/list?api_key=&language=zh
    # http://api.themoviedb.org/3/genre/tv/list?api_key=&language=zh
    genre_map = {
        'Sci-Fi & Fantasy': 'Sci-Fi',
        'War & Politics':   'War',
        '儿童':             'Kids',
        '冒险':             'Adventure',
        '剧情':             'Drama',
        '动作':             'Action',
        '动作冒险':         'Action',
        '动画':             'Animation',
        '历史':             'History',
        '喜剧':             'Comedy',
        '奇幻':             'Fantasy',
        '家庭':             'Family',
        '恐怖':             'Horror',
        '悬疑':             'Mystery',
        '惊悚':             'Thriller',
        '战争':             'War',
        '新闻':             'News',
        '爱情':             'Romance',
        '犯罪':             'Crime',
        '电视电影':         'TV Movie',
        '真人秀':           'Reality-TV',
        '科幻':             'Sci-Fi',
        '纪录':             'Documentary',
        '肥皂剧':           'Soap',
        '脱口秀':           'Talk-Show',
        '西部':             'Western',
        '音乐':             'Music',
    }

    def scrape(self, url):
        m = self.regex.match(url)
        if m:
            effective_url = m[0]
        else:
            raise ValueError("not valid url")
        effective_url = m[0]
        is_series = m[1] == 'tv'
        id = m[2]
        if is_series:
            api_url = f"https://api.themoviedb.org/3/tv/{id}?api_key={settings.TMDB_API3_KEY}&language=zh-CN&append_to_response=external_ids,credits"
        else:
            api_url = f"https://api.themoviedb.org/3/movie/{id}?api_key={settings.TMDB_API3_KEY}&language=zh-CN&append_to_response=external_ids,credits"
        r = requests.get(api_url)
        res_data = r.json()

        if is_series:
            title = res_data['name']
            orig_title = res_data['original_name']
            year = int(res_data['first_air_date'].split('-')[0])
            imdb_code = res_data['external_ids']['imdb_id']
            showtime = [{res_data['first_air_date']: "首播日期"}]
            duration = None
        else:
            title = res_data['title']
            orig_title = res_data['original_title']
            year = int(res_data['release_date'].split('-')[0])
            showtime = [{res_data['release_date']: "发布日期"}]
            imdb_code = res_data['imdb_id']
            duration = res_data['runtime']  # in minutes

        genre = list(map(lambda x: self.genre_map[x['name']] if x['name'] in self.genre_map else 'Other', res_data['genres']))
        language = list(map(lambda x: x['name'], res_data['spoken_languages']))
        brief = res_data['overview']

        if is_series:
            director = list(map(lambda x: x['name'], res_data['created_by']))
        else:
            director = list(map(lambda x: x['name'], filter(lambda c: c['job'] == 'Director', res_data['credits']['crew'])))
        playwright = list(map(lambda x: x['name'], filter(lambda c: c['job'] == 'Screenplay', res_data['credits']['crew'])))
        actor = list(map(lambda x: x['name'], res_data['credits']['cast']))
        area = []

        other_info = {}
        other_info['TMDB评分'] = res_data['vote_average']
        # other_info['分级'] = res_data['contentRating']
        # other_info['Metacritic评分'] = res_data['metacriticRating']
        # other_info['奖项'] = res_data['awards']
        other_info['TMDB_ID'] = id
        if is_series:
            other_info['Seasons'] = res_data['number_of_seasons']
            other_info['Episodes'] = res_data['number_of_episodes']

        img_url = 'https://image.tmdb.org/t/p/original/' + res_data['poster_path']  # TODO: use GET /configuration to get base url
        raw_img, ext = self.download_image(img_url, url)

        data = {
            'title': title,
            'orig_title': orig_title,
            'other_title': None,
            'imdb_code': imdb_code,
            'director': director,
            'playwright': playwright,
            'actor': actor,
            'genre': genre,
            'showtime': showtime,
            'site': None,
            'area': area,
            'language': language,
            'year': year,
            'duration': duration,
            'season': None,
            'episodes': None,
            'single_episode_length': None,
            'brief': brief,
            'is_series': is_series,
            'other_info': other_info,
            'source_site': self.site_name,
            'source_url': effective_url,
        }
        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img

    @classmethod
    def get_effective_url(cls, raw_url):
        m = cls.regex.match(raw_url)
        if raw_url:
            return m[0]
        else:
            return None

# https://developers.google.com/youtube/v3/docs/?apix=true
# https://developers.google.com/books/docs/v1/using
class GoogleBooksScraper(AbstractScraper):
    site_name = SourceSiteEnum.GOOGLEBOOKS.value
    host = "books.google.com"
    data_class = Book
    form_class = BookForm
    regex = re.compile(r"https://books\.google\.com/books\?id=([^&#]+)")

    @classmethod
    def get_effective_url(cls, raw_url):
        u = re.match(r"https://books\.google\.com/books\?id=[^&#]+", raw_url)
        return u[0] if u else None

    def scrape(self, url, response=None):
        m = self.regex.match(url)
        if m:
            api_url = f'https://www.googleapis.com/books/v1/volumes/{m[1]}'
        else:
            raise ValueError("not valid url")
        b = requests.get(api_url).json()
        other = {}
        title = b['volumeInfo']['title']
        subtitle = b['volumeInfo']['subtitle'] if 'subtitle' in b['volumeInfo'] else None
        pub_year = None
        pub_month = None
        if 'publishedDate' in b['volumeInfo']:
            pub_date = b['volumeInfo']['publishedDate']
            pub_year = re.sub(r'(\d\d\d\d).+', r'\1', pub_date)
            pub_month = re.sub(r'(\d\d\d\d)-(\d+).+', r'\2', pub_date) if len(pub_date) > 5 else None
        pub_house = b['volumeInfo']['publisher'] if 'publisher' in b['volumeInfo'] else None
        language = b['volumeInfo']['language'] if 'language' in b['volumeInfo'] else None
        pages = b['volumeInfo']['pageCount'] if 'pageCount' in b['volumeInfo'] else None
        if 'mainCategory' in b['volumeInfo']:
            other['分类'] = b['volumeInfo']['mainCategory']
        authors = b['volumeInfo']['authors'] if 'authors' in b['volumeInfo'] else None
        if 'description' in b['volumeInfo']:
            brief = b['volumeInfo']['description']
        elif 'textSnippet' in b['volumeInfo']:
            brief = b["volumeInfo"]["textSnippet"]["searchInfo"]
        else:
            brief = ''
        brief = re.sub(r'<.*?>', '', brief.replace('<br', '\n<br'))
        img_url = b['volumeInfo']['imageLinks']['thumbnail'] if 'imageLinks' in b['volumeInfo'] else None
        isbn10 = None
        isbn13 = None
        for iid in b['volumeInfo']['industryIdentifiers'] if 'industryIdentifiers' in b['volumeInfo'] else []:
            if iid['type'] == 'ISBN_10':
                isbn10 = iid['identifier']
            if iid['type'] == 'ISBN_13':
                isbn13 = iid['identifier']
        isbn = isbn13 if isbn13 is not None else isbn10

        data = {
            'title': title,
            'subtitle': subtitle,
            'orig_title': None,
            'author': authors,
            'translator': None,
            'language': language,
            'pub_house': pub_house,
            'pub_year': pub_year,
            'pub_month': pub_month,
            'binding': None,
            'pages': pages,
            'isbn': isbn,
            'brief': brief,
            'contents': None,
            'other_info': other,
            'cover_url': img_url,
            'source_site': self.site_name,
            'source_url': self.get_effective_url(url),
        }
        raw_img, ext = self.download_image(img_url, url)

        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img
