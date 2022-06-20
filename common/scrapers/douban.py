import requests
import re
import filetype
from lxml import html
from common.models import SourceSiteEnum
from movies.models import Movie, MovieGenreEnum
from movies.forms import MovieForm
from books.models import Book
from books.forms import BookForm
from music.models import Album
from music.forms import AlbumForm
from games.models import Game
from games.forms import GameForm
from django.core.validators import URLValidator
from django.conf import settings
from PIL import Image
from io import BytesIO
from common.scraper import *


class DoubanScrapperMixin:
    @classmethod
    def download_page(cls, url, headers):
        url = cls.get_effective_url(url)
        r = None
        error = 'DoubanScrapper: error occured when downloading ' + url
        content = None
        last_error = None

        def get(url):
            nonlocal r
            # print('Douban GET ' + url)
            try:
                r = requests.get(url, timeout=settings.SCRAPING_TIMEOUT)
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
                    if content.find('你的 IP 发出') == -1:
                        error = error + 'Content not authentic'  # response is garbage
                    else:
                        error = error + 'IP banned'
                    content = None
                    last_error = 'network'
                elif content.find('<title>页面不存在</title>') != -1:  # re.search('不存在[^<]+</title>', content, re.MULTILINE):
                    content = None
                    last_error = 'censorship'
                    error = error + 'Not found or hidden by Douban'
            else:
                last_error = 'network'
                error = error + str(r.status_code)  # logged in user may see 204 for cencered item

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
            get('http://archive.org/wayback/available?url=' + url)
            if r.status_code == 200:
                w = r.json()
                if w['archived_snapshots'] and w['archived_snapshots']['closest']:
                    get(w['archived_snapshots']['closest']['url'])
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
            get('http://web.archive.org/cdx/search/cdx?url=' + url)
            if r.status_code == 200:
                dates = re.findall(r'[^\s]+\s+(\d+)\s+[^\s]+\s+[^\s]+\s+\d+\s+[^\s]+\s+\d{5,}',
                                   r.content.decode('utf-8'))
                # assume snapshots whose size >9999 contain real content, use the latest one of them
                if len(dates) > 0:
                    get('http://web.archive.org/web/' + dates[-1] + '/' + url)
                    check_content()
                    if content is not None:
                        fix_wayback_links()
                else:
                    error = error + 'No snapshot available'
            else:
                error = error + str(r.status_code)

        def latest():
            nonlocal r, error, content
            if settings.LOCAL_PROXY is not None:
                error = error + '\nLocal: '
                get(f'{settings.LOCAL_PROXY}?url={url}')
            elif settings.SCRAPESTACK_KEY is not None:
                error = error + '\nScrapeStack: '
                get(f'http://api.scrapestack.com/scrape?access_key={settings.SCRAPESTACK_KEY}&url={url}')
            elif settings.SCRAPERAPI_KEY is not None:
                error = error + '\nScraperAPI: '
                get(f'http://api.scraperapi.com?api_key={settings.SCRAPERAPI_KEY}&url={url}')
            else:
                error = error + '\nDirect: '
                get(url)
            check_content()
            if last_error == 'network' and settings.LOCAL_PROXY is None and settings.PROXYCRAWL_KEY is not None:
                error = error + '\nProxyCrawl: '
                get(f'https://api.proxycrawl.com/?token={settings.PROXYCRAWL_KEY}&url={url}')
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

        if settings.SCRAPESTACK_KEY is not None:
            dl_url = f'http://api.scrapestack.com/scrape?access_key={settings.SCRAPESTACK_KEY}&url={url}'
        elif settings.SCRAPERAPI_KEY is not None:
            dl_url = f'http://api.scraperapi.com?api_key={settings.SCRAPERAPI_KEY}&url={url}'
        else:
            dl_url = url

        try:
            img_response = requests.get(dl_url, timeout=settings.SCRAPING_TIMEOUT)
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
                img_response = requests.get(dl_url, timeout=settings.SCRAPING_TIMEOUT)
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
        subtitle = subtitle_elem[0].strip()[:500] if subtitle_elem else None

        orig_title_elem = content.xpath(
            "//div[@id='info']//span[text()='原作名:']/following::text()")
        orig_title = orig_title_elem[0].strip()[:500] if orig_title_elem else None

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
        pub_year = None if pub_year is not None and pub_year not in range(
            0, 3000) else pub_year
        pub_month = None if pub_month is not None and pub_month not in range(
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
                authors.append(RE_WHITESPACES.sub(' ', author.strip())[:200])
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
        actor = actor_elem[:200] if actor_elem else None

        # construct genre translator
        genre_translator = {}
        attrs = [attr for attr in dir(MovieGenreEnum) if '__' not in attr]
        for attr in attrs:
            genre_translator[getattr(MovieGenreEnum, attr).label] = getattr(
                MovieGenreEnum, attr).value

        genre_elem = content.xpath("//span[@property='v:genre']/text()")
        if genre_elem:
            genre = []
            for g in genre_elem:
                g = g.split(' ')[0]
                if g == '紀錄片':  # likely some original data on douban was corrupted
                    g = '纪录片'
                elif g == '鬼怪':
                    g = '惊悚'
                elif g == 'News':
                    g = '新闻'
                if g in genre_translator:
                    genre.append(genre_translator[g])
                else:
                    logger.error(f'unable to map genre {g}')
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
        site = site_elem[0].strip()[:200] if site_elem else None
        try:
            validator = URLValidator()
            validator(site)
        except ValidationError:
            site = None

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
        year = int(re.search(r'\d+', year_elem[0])[0]) if year_elem and re.search(r'\d+', year_elem[0]) else None

        duration_elem = content.xpath("//span[@property='v:runtime']/text()")
        other_duration_elem = content.xpath(
            "//span[@property='v:runtime']/following-sibling::text()[1]")
        if duration_elem:
            duration = duration_elem[0].strip()
            if other_duration_elem:
                duration += other_duration_elem[0].rstrip()
            duration = duration.split('/')[0].strip()
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
        episodes = int(episodes_elem[0].strip()) if episodes_elem and episodes_elem[0].isdigit() else None

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

        artists_elem = content.xpath("//div[@id='info']/span/span[@class='pl']/a/text()")
        artist = None if not artists_elem else artists_elem[:200]

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
