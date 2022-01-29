from django.core.management.base import BaseCommand
from django.core.files.uploadedfile import SimpleUploadedFile
from common.scraper import *
from django.conf import settings
from movies.models import Movie
from movies.forms import MovieForm
import requests
import re
import filetype
from lxml import html
from PIL import Image
from io import BytesIO


class DoubanPatcherMixin:
    @classmethod
    def download_page(cls, url, headers):
        url = cls.get_effective_url(url)
        r = None
        error = 'DoubanScrapper: error occured when downloading ' + url
        content = None

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
            nonlocal r, error, content
            content = None
            if r.status_code == 200:
                content = r.content.decode('utf-8')
                if content.find('关于豆瓣') == -1:
                    if content.find('你的 IP 发出') == -1:
                        error = error + 'Content not authentic'  # response is garbage
                    else:
                        error = error + 'IP banned'
                    content = None
                elif re.search('不存在[^<]+</title>', content, re.MULTILINE):
                    content = None
                    error = error + 'Not found or hidden by Douban'
            else:
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
            if settings.SCRAPESTACK_KEY is None:
                error = error + '\nDirect: '
                get(url, 60)
            else:
                error = error + '\nScraperAPI: '
                get(f'http://api.scrapestack.com/scrape?access_key={settings.SCRAPESTACK_KEY}&url={url}', 60)
            check_content()

        # wayback_cdx()
        # if content is None:
        latest()

        if content is None:
            logger.error(error)
            content = '<html />'
        # with open('/tmp/temp.html', 'w', encoding='utf-8') as fp:
        #     fp.write(content)
        return html.fromstring(content)

    @classmethod
    def download_image(cls, url, item_url=None):
        if url is None:
            return None, None
        raw_img = None
        ext = None

        dl_url = url
        if settings.SCRAPESTACK_KEY is not None:
            dl_url = f'http://api.scrapestack.com/scrape?access_key={settings.SCRAPESTACK_KEY}&url={url}'

        try:
            img_response = requests.get(dl_url, timeout=90)
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
        if raw_img is None and settings.SCRAPESTACK_KEY is not None:
            try:
                img_response = requests.get(dl_url, timeout=90)
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


class DoubanMoviePatcher(DoubanPatcherMixin, AbstractScraper):
    site_name = SourceSiteEnum.DOUBAN.value
    host = 'movie.douban.com'
    data_class = Movie
    form_class = MovieForm

    regex = re.compile(r"https://movie\.douban\.com/subject/\d+/{0,1}")

    def scrape(self, url):
        headers = DEFAULT_REQUEST_HEADERS.copy()
        headers['Host'] = self.host
        content = self.download_page(url, headers)
        img_url_elem = content.xpath("//img[@rel='v:image']/@src")
        img_url = img_url_elem[0].strip() if img_url_elem else None
        raw_img, ext = self.download_image(img_url, url)
        return raw_img, ext


class Command(BaseCommand):
    help = 'fix cover image'

    def add_arguments(self, parser):
        parser.add_argument('threadId', type=int, help='% 8')

    def handle(self, *args, **options):
        t = int(options['threadId'])
        for m in Movie.objects.filter(cover='movie/default.svg', source_site='douban'):
            if m.id % 8 == t:
                print(f'Re-fetching {m.source_url}')
                try:
                    raw_img, img_ext = DoubanMoviePatcher.scrape(m.source_url)
                    if img_ext is not None:
                        m.cover = SimpleUploadedFile('temp.' + img_ext, raw_img)
                        m.save()
                        print(f'Saved {m.source_url}')
                    else:
                        print(f'Skipped {m.source_url}')
                except Exception as e:
                    print(e)
            # return
