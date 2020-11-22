import requests
import functools
import random
import logging
from lxml import html
import re
from boofilsic.settings import LUMINATI_USERNAME, LUMINATI_PASSWORD, DEBUG
from django.utils.translation import ugettext_lazy as _
from movies.models import MovieGenreEnum
from common.models import SourceSiteEnum


RE_NUMBERS = re.compile(r"\d+\d*")
RE_WHITESPACES = re.compile(r"\s+")


DEFAULT_REQUEST_HEADERS = {
    'Host': 'book.douban.com',
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


# register all implemented scraper in form of {host: class,}
registry = {}


def log_url(func):
    """
    Catch exceptions and log then pass the exceptions.
    First postion argument of decorated function must be the url.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # log the url
            logger.error(f"Scrape Failed URL: {args[0]}")
            logger.error(str(e))
            raise e

    return wrapper


class AbstractScraper:

    # subclasses must specify those two variables
    site = None
    host = None

    def __init_subclass__(cls, **kwargs):
        # this statement initialize the subclasses
        super().__init_subclass__(**kwargs)
        assert cls.site is not None, "class variable `site` must be specified"
        assert cls.host is not None, "class variable `host` must be specified"
        assert isinstance(cls.host, str), "`host` must be type str"
        assert isinstance(cls.site, int), "`site` must be type int"
        assert hasattr(cls, 'scrape') and callable(cls.scrape), "scaper must have method `.scrape()`"
        # decorate the scrape method
        cls.scrape = classmethod(log_url(cls.scrape))
        registry[cls.host] = cls


    def scrape(self, url):
        """
        Scrape/request model schema specified data from given url and return it.
        Implementations of subclasses to this method would be decorated as class method.
        """
        raise NotImplementedError("Subclass should implement this method")

    @classmethod
    def download_page(cls, url, regex, headers):
        url = regex.findall(url)
        if not url:
            raise ValueError("not valid url")
        else:
            url = url[0] + '/'

        session_id = random.random()
        proxy_url = ('http://%s-country-cn-session-%s:%s@zproxy.lum-superproxy.io:%d' %
                    (LUMINATI_USERNAME, session_id, LUMINATI_PASSWORD, PORT))
        proxies = {
            'http': proxy_url,
            'https': proxy_url,
        }
        # if DEBUG:
        #     proxies = None
        r = requests.get(url, proxies=proxies, headers=headers, timeout=TIMEOUT)
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
        return raw_img


class DoubanBookScraper(AbstractScraper):
    site = SourceSiteEnum.DOUBAN.value
    host = "book.douban.com"
    regex = re.compile(r"https://book.douban.com/subject/\d+")

    def scrape(self, url):
        regex = self.regex
        headers = DEFAULT_REQUEST_HEADERS.copy()
        headers['Host'] = self.host
        content = self.download_page(url, regex, headers)

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
        brief = '\n'.join(p.strip() for p in brief_elem) if brief_elem else None

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
        raw_img = self.download_image(img_url)

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
            'other_info': other
        }
        return data, raw_img


class DoubanMovieScraper(AbstractScraper):
    site = SourceSiteEnum.DOUBAN.value
    host = 'movie.douban.com'
    regex = re.compile(r"https://movie.douban.com/subject/\d+")

    def scrape(self, url):
        regex = self.regex
        headers = DEFAULT_REQUEST_HEADERS.copy()
        headers['Host'] = 'movie.douban.com'
        content = self.download_page(url, regex, headers)

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
        raw_img = self.download_image(img_url)

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
        }
        return data, raw_img
 