import re
from common.models import SourceSiteEnum
from movies.models import Movie, MovieGenreEnum
from movies.forms import MovieForm
from books.models import Book
from books.forms import BookForm
from music.models import Album, Song
from music.forms import AlbumForm, SongForm
from games.models import Game
from games.forms import GameForm
from common.scraper import *


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
