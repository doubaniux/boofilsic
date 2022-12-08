import re
from catalog.book.models import Edition
from catalog.common import *
from lxml import html
import json
import logging


logger = logging.getLogger(__name__)


class GoodreadsDownloader(RetryDownloader):
    def validate_response(self, response):
        if response is None:
            return RESPONSE_NETWORK_ERROR
        elif response.status_code == 200:
            if response.text.find('__NEXT_DATA__') != -1:
                return RESPONSE_OK
            else:  # retry if return legacy version
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
            content = response.text
        else:
            dl = GoodreadsDownloader(self.url)
            content = dl.download().text
        h = html.fromstring(content.strip())
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
            raise ParseError(self, 'Book json')
        data['title'] = b['title']
        data['brief'] = b['description']
        data['isbn'] = b['details'].get('isbn13')
        asin = b['details'].get('asin')
        if asin and asin != data['isbn']:
            data['asin'] = asin
        data['pages'] = b['details'].get('numPages')
        data['cover_image_url'] = b['imageUrl']
        data['work'] = {}
        w = next(filter(lambda x: x.get('details'), o['Work']), None)
        if w:
            data['work']['lookup_id_type'] = IdType.Goodreads_Work
            data['work']['lookup_id_value'] = str(w['legacyId'])
            data['work']['title'] = w['details']['originalTitle']
            data['work']['url'] = w['details']['webUrl']

        pd = PageData(metadata=data)
        pd.lookup_ids[IdType.ISBN] = data.get('isbn')
        pd.lookup_ids[IdType.ASIN] = data.get('asin')
        if data["cover_image_url"]:
            imgdl = BasicImageDownloader(data["cover_image_url"], self.url)
            try:
                pd.cover_image = imgdl.download().content
                pd.cover_image_extention = imgdl.extention
            except Exception:
                logger.debug(f'failed to download cover for {self.url} from {data["cover_image_url"]}')
        return pd
