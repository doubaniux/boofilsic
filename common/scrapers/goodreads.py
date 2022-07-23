import requests
import re
import filetype
from lxml import html
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
from common.scraper import *


class GoodreadsScraper(AbstractScraper):
    site_name = SourceSiteEnum.GOODREADS.value
    host = "www.goodreads.com"
    data_class = Book
    form_class = BookForm
    regex = re.compile(r"https://www\.goodreads\.com/book/show/\d+")

    @classmethod
    def get_effective_url(cls, raw_url):
        u = re.match(r".+(/book/show/\d+)", raw_url)
        return "https://www.goodreads.com" + u[1] if u else None

    def scrape(self, url, response=None):
        """
        This is the scraping portal
        """
        if response is not None:
            content = html.fromstring(response.content.decode('utf-8'))
        else:
            headers = None  # DEFAULT_REQUEST_HEADERS.copy()
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
