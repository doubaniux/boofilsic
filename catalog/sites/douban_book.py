from lxml import html
from catalog.common import *
from .douban import *
from catalog.book.models import *
from catalog.book.utils import *
import logging


logger = logging.getLogger(__name__)


@SiteList.register
class DoubanBook(AbstractSite, ScraperMixin):
    ID_TYPE = IdType.DoubanBook
    URL_PATTERNS = [r"\w+://book\.douban\.com/subject/(\d+)/{0,1}", r"\w+://m.douban.com/book/subject/(\d+)/{0,1}"]
    WIKI_PROPERTY_ID = '?'
    DEFAULT_MODEL = Edition

    @classmethod
    def id_to_url(self, id_value):
        return "https://book.douban.com/subject/" + id_value + "/"

    def scrape(self):
        self.data = {}
        self.html = html.fromstring(DoubanDownloader(self.url).download().text.strip())
        self.parse_field('title', "/html/body//h1/span/text()")
        self.parse_field('isbn', "//div[@id='info']//span[text()='ISBN:']/following::text()")
        # TODO does douban store ASIN as ISBN, need more cleanup if so
        if not self.data['title']:
            if self.data['isbn']:
                self.data['title'] = 'isbn: ' + isbn
            else:
                raise ParseError(self, 'title')

        self.parse_field('cover_image_url', "//*[@id='mainpic']/a/img/@src")
        self.parse_field('brief', "//h2/span[text()='内容简介']/../following-sibling::div[1]//div[@class='intro'][not(ancestor::span[@class='short'])]/p/text()")
        self.parse_field('series', "//div[@id='info']//span[text()='丛书:']/following-sibling::a[1]/text()")
        self.parse_field('producer', "//div[@id='info']//span[text()='出品方:']/following-sibling::a[1]/text()")
        self.parse_field('cubn', "//div[@id='info']//span[text()='统一书号:']/following::text()")
        self.parse_field('subtitle', "//div[@id='info']//span[text()='副标题:']/following::text()")
        self.parse_field('orig_title', "//div[@id='info']//span[text()='原作名:']/following::text()")
        self.parse_field('language', "//div[@id='info']//span[text()='语言:']/following::text()")
        self.parse_field('pub_house', "//div[@id='info']//span[text()='出版社:']/following::text()")
        self.parse_field('pub_date', "//div[@id='info']//span[text()='出版年:']/following::text()")
        year_month_day = RE_NUMBERS.findall(self.data['pub_date']) if self.data['pub_date'] else []
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

        self.parse_field('binding', "//div[@id='info']//span[text()='装帧:']/following::text()")
        self.parse_field('price', "//div[@id='info']//span[text()='定价:']/following::text()")
        self.parse_field('pages', "//div[@id='info']//span[text()='页数:']/following::text()")
        if self.data['pages'] is not None:
            self.data['pages'] = int(RE_NUMBERS.findall(self.data['pages'])[0]) if RE_NUMBERS.findall(self.data['pages']) else None
            if self.data['pages'] and (self.data['pages'] > 999999 or self.data['pages'] < 1):
                self.data['pages'] = None

        contents = None
        try:
            contents_elem = self.html.xpath(
                "//h2/span[text()='目录']/../following-sibling::div[1]")[0]
            # if next the id of next sibling contains `dir`, that would be the full contents
            if "dir" in contents_elem.getnext().xpath("@id")[0]:
                contents_elem = contents_elem.getnext()
                contents = '\n'.join(p.strip() for p in contents_elem.xpath("text()")[:-2]) if len(contents_elem) else None
            else:
                contents = '\n'.join(p.strip() for p in contents_elem.xpath("text()")) if len(contents_elem) else None
        except Exception:
            pass
        self.data['contents'] = contents

        # there are two html formats for authors and translators
        authors_elem = self.html.xpath("""//div[@id='info']//span[text()='作者:']/following-sibling::br[1]/
            preceding-sibling::a[preceding-sibling::span[text()='作者:']]/text()""")
        if not authors_elem:
            authors_elem = self.html.xpath(
                """//div[@id='info']//span[text()=' 作者']/following-sibling::a/text()""")
        if authors_elem:
            authors = []
            for author in authors_elem:
                authors.append(RE_WHITESPACES.sub(' ', author.strip())[:200])
        else:
            authors = None
        self.data['authors'] = authors

        translators_elem = self.html.xpath("""//div[@id='info']//span[text()='译者:']/following-sibling::br[1]/
            preceding-sibling::a[preceding-sibling::span[text()='译者:']]/text()""")
        if not translators_elem:
            translators_elem = self.html.xpath(
                """//div[@id='info']//span[text()=' 译者']/following-sibling::a/text()""")
        if translators_elem:
            translators = []
            for translator in translators_elem:
                translators.append(RE_WHITESPACES.sub(' ', translator.strip()))
        else:
            translators = None
        self.data['translators'] = translators

        work_link = self.parse_str('//h2/span[text()="这本书的其他版本"]/following-sibling::span[@class="pl"]/a/@href')
        if work_link:
            r = re.match(r'\w+://book.douban.com/works/(\d+)', work_link)
            self.data['required_pages'] = [{
                'model': 'Work',
                'id_type': IdType.DoubanBook_Work, 
                'id_value': r[1] if r else None,
                'title': self.data['title'],
                'url': work_link,
            }]
        pd = PageData(metadata=self.data)
        pd.lookup_ids[IdType.ISBN] = self.data.get('isbn')
        pd.lookup_ids[IdType.CUBN] = self.data.get('cubn')
        if self.data["cover_image_url"]:
            imgdl = BasicImageDownloader(self.data["cover_image_url"], self.url)
            try:
                pd.cover_image = imgdl.download().content
                pd.cover_image_extention = imgdl.extention
            except Exception:
                logger.debug(f'failed to download cover for {self.url} from {self.data["cover_image_url"]}')
        return pd


@SiteList.register
class DoubanBook_Work(AbstractSite):
    ID_TYPE = IdType.DoubanBook_Work
    URL_PATTERNS = [r"\w+://book\.douban\.com/works/(\d+)"]
    WIKI_PROPERTY_ID = '?'
    DEFAULT_MODEL = Work

    @classmethod
    def id_to_url(self, id_value):
        return "https://book.douban.com/works/" + id_value + "/"

    def bypass_scrape(self, data_from_link):
        if not data_from_link:
            return None
        pd = PageData(metadata={
            'title': data_from_link['title'],
        })
        return pd

    def scrape(self):
        content = html.fromstring(DoubanDownloader(self.url).download().text.strip())
        title_elem = content.xpath("//h1/text()")
        title = title_elem[0].split('全部版本(')[0].strip() if title_elem else None
        if not title:
            raise ParseError(self, 'title')
        pd = PageData(metadata={
            'title': title,
        })
        return pd
