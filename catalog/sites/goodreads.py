import re
from catalog.book.models import Edition, Work
from catalog.common import *
from lxml import html
import json
import logging


_logger = logging.getLogger(__name__)


class GoodreadsDownloader(RetryDownloader):
    def validate_response(self, response):
        if response is None:
            return RESPONSE_NETWORK_ERROR
        elif response.status_code == 200:
            if response.text.find('__NEXT_DATA__') != -1:
                return RESPONSE_OK
            else:
                # Goodreads may return legacy version for a/b testing
                # retry if so
                return RESPONSE_NETWORK_ERROR
        else:
            return RESPONSE_INVALID_CONTENT


@SiteList.register
class Goodreads(AbstractSite):
    ID_TYPE = IdType.Goodreads
    WIKI_PROPERTY_ID = 'P2968'
    DEFAULT_MODEL = Edition
    URL_PATTERNS = [r".+goodreads.com/.*book/show/(\d+)", r".+goodreads.com/.*book/(\d+)"]

    @classmethod
    def id_to_url(self, id_value):
        return "https://www.goodreads.com/book/show/" + id_value

    def scrape(self, response=None):
        data = {}
        if response is not None:
            h = html.fromstring(response.text.strip())
        else:
            dl = GoodreadsDownloader(self.url)
            h = dl.download().html()
        # Next.JS version of GoodReads
        # JSON.parse(document.getElementById('__NEXT_DATA__').innerHTML)['props']['pageProps']['apolloState']
        elem = h.xpath('//script[@id="__NEXT_DATA__"]/text()')
        src = elem[0].strip() if elem else None
        if not src:
            raise ParseError(self, '__NEXT_DATA__ element')
        d = json.loads(src)['props']['pageProps']['apolloState']
        o = {'Book': [], 'Work': [], 'Series': [], 'Contributor': []}
        for v in d.values():
            t = v.get('__typename')
            if t and t in o:
                o[t].append(v)
        b = next(filter(lambda x: x.get('title'), o['Book']), None)
        if not b:
            # Goodreads may return empty page template when internal service timeouts
            raise ParseError(self, 'Book in __NEXT_DATA__ json')
        data['title'] = b['title']
        data['brief'] = b['description']
        data['isbn'] = b['details'].get('isbn13')
        asin = b['details'].get('asin')
        if asin and asin != data['isbn']:
            data['asin'] = asin
        data['pages'] = b['details'].get('numPages')
        data['cover_image_url'] = b['imageUrl']
        w = next(filter(lambda x: x.get('details'), o['Work']), None)
        if w:
            data['required_resources'] = [{
                'model': 'Work',
                'id_type': IdType.Goodreads_Work,
                'id_value': str(w['legacyId']),
                'title': w['details']['originalTitle'],
                'url': w['editions']['webUrl'],
            }]
        pd = ResourceContent(metadata=data)
        pd.lookup_ids[IdType.ISBN] = data.get('isbn')
        pd.lookup_ids[IdType.ASIN] = data.get('asin')
        if data["cover_image_url"]:
            imgdl = BasicImageDownloader(data["cover_image_url"], self.url)
            try:
                pd.cover_image = imgdl.download().content
                pd.cover_image_extention = imgdl.extention
            except Exception:
                _logger.debug(f'failed to download cover for {self.url} from {data["cover_image_url"]}')
        return pd


@SiteList.register
class Goodreads_Work(AbstractSite):
    ID_TYPE = IdType.Goodreads_Work
    WIKI_PROPERTY_ID = ''
    DEFAULT_MODEL = Work
    URL_PATTERNS = [r".+goodreads.com/work/editions/(\d+)"]

    @classmethod
    def id_to_url(self, id_value):
        return "https://www.goodreads.com/work/editions/" + id_value

    def scrape(self, response=None):
        content = BasicDownloader(self.url).download().html()
        title_elem = content.xpath("//h1/a/text()")
        title = title_elem[0].strip() if title_elem else None
        if not title:
            raise ParseError(self, 'title')
        author_elem = content.xpath("//h2/a/text()")
        author = author_elem[0].strip() if author_elem else None
        first_published_elem = content.xpath("//h2/span/text()")
        first_published = first_published_elem[0].strip() if first_published_elem else None
        pd = ResourceContent(metadata={
            'title': title,
            'author': author,
            'first_published': first_published
        })
        return pd
