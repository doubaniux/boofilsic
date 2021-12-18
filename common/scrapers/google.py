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
            pub_date = b['volumeInfo']['publishedDate'].split('-')
            pub_year = pub_date[0]
            pub_month = pub_date[1] if len(pub_date) > 1 else None
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
