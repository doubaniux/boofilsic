import requests
import functools
import random
import logging
import re
import dateparser
import datetime
import time
from lxml import html
from mimetypes import guess_extension
from threading import Thread
from boofilsic.settings import LUMINATI_USERNAME, LUMINATI_PASSWORD, DEBUG
from boofilsic.settings import SPOTIFY_CREDENTIAL
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
TIMEOUT = 10

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
            logger.error(f"Scrape Failed URL: {args[1]}")
            logger.error("Expections during scraping:", exc_info=e)
            raise e

    return wrapper


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
        url = cls.regex.findall(raw_url)
        if not url:
            raise ValueError("not valid url")
        return url[0]

    @classmethod
    def download_page(cls, url, headers):
        url = cls.get_effective_url(url)

        session_id = random.random()
        proxy_url = ('http://%s-country-cn-session-%s:%s@zproxy.lum-superproxy.io:%d' %
                     (LUMINATI_USERNAME, session_id, LUMINATI_PASSWORD, PORT))
        proxies = {
            'http': proxy_url,
            'https': proxy_url,
        }
        # if DEBUG:
        #     proxies = None
        r = requests.get(url, proxies=proxies,
                         headers=headers, timeout=TIMEOUT)
        # r = requests.get(url, headers=DEFAULT_REQUEST_HEADERS, timeout=TIMEOUT)

        return html.fromstring(r.content.decode('utf-8'))

    @classmethod
    def download_image(cls, url):
        if url is None:
            return
        raw_img = None
        session_id = random.random()
        proxy_url = ('http://%s-country-cn-session-%s:%s@zproxy.lum-superproxy.io:%d' %
                     (LUMINATI_USERNAME, session_id, LUMINATI_PASSWORD, PORT))
        proxies = {
            'http': proxy_url,
            'https': proxy_url,
        }
        # if DEBUG:
        #     proxies = None
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
                ext = guess_extension(content_type.partition(';')[0].strip())
        return raw_img, ext


    @classmethod
    def save(cls, request_user):
        entity_cover = {
            'cover': SimpleUploadedFile('temp' + cls.img_ext, cls.raw_img)
        }
        form = cls.form_class(cls.raw_data, entity_cover)
        if form.is_valid():
            form.instance.last_editor = request_user
            form.save()
            cls.instance = form.instance
        else:
            logger.error(str(form.errors))
            raise ValidationError("Form invalid.")
        return form


class DoubanBookScraper(AbstractScraper):
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
        except:
            pass

        img_url_elem = content.xpath("//*[@id='mainpic']/a/img/@src")
        img_url = img_url_elem[0].strip() if img_url_elem else None
        raw_img, ext = self.download_image(img_url)

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


class DoubanMovieScraper(AbstractScraper):
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
        raw_img, ext = self.download_image(img_url)

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


class DoubanAlbumScraper(AbstractScraper):
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
        release_date = dateparser.parse(date_elem[0].strip(), settings={
                                        "RELATIVE_BASE": datetime.datetime(1900, 1, 1)}) if date_elem else None

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
        raw_img, ext = self.download_image(img_url)

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
    # API URL
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

        release_date = dateparser.parse(
            res_data['album']['release_date'],
            settings={
                "RELATIVE_BASE": datetime.datetime(1900, 1, 1)
            }
        )

        duration = res_data['duration_ms']

        if res_data['external_ids'].get('isrc'):
            isrc = res_data['external_ids']['isrc']
        else:
            isrc = None

        raw_img, ext = self.download_image(res_data['album']['images'][0]['url'])
        
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


        release_date = dateparser.parse(
            res_data['release_date'],
            settings={
                "RELATIVE_BASE": datetime.datetime(1900, 1, 1)
            }
        )

        other_info = {}
        if res_data['external_ids'].get('upc'):
            # bar code
            other_info['UPC'] = res_data['external_ids']['upc']

        raw_img, ext = self.download_image(res_data['images'][0]['url'])

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
            "Authorization": f"Basic {SPOTIFY_CREDENTIAL}"
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
                "Authorization": f"Basic {SPOTIFY_CREDENTIAL}"
            }
        )
        data = r.json()
    elif r.status_code != 200:
        raise Exception(f"Request to spotify API fails. Reason: {r.reason}")
    # minus 2 for execution time error
    spotify_token_expire_time = int(data['expires_in']) + time.time() - 2
    spotify_token = data['access_token']
