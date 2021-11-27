import re
import dateparser
import json
from lxml import html
from common.models import SourceSiteEnum
from common.scraper import AbstractScraper
from music.models import Album
from music.forms import AlbumForm


class BandcampAlbumScraper(AbstractScraper):
    site_name = SourceSiteEnum.BANDCAMP.value
    # API URL
    host = '.bandcamp.com/'
    data_class = Album
    form_class = AlbumForm

    regex = re.compile(r"https://[\w-]+\.bandcamp\.com/album/[^?#]+")

    def scrape(self, url, response=None):
        effective_url = self.get_effective_url(url)
        if effective_url is None:
            raise ValueError("not valid url")
        if response is not None:
            content = html.fromstring(response.content.decode('utf-8'))
        else:
            content = self.download_page(url, {})
        try:
            title = content.xpath("//h2[@class='trackTitle']/text()")[0].strip()
            artist = [content.xpath("//div[@id='name-section']/h3/span/a/text()")[0].strip()]
        except IndexError:
            raise ValueError("given url contains no valid info")

        genre = []  # TODO: parse tags
        track_list = []
        release_nodes = content.xpath("//div[@class='tralbumData tralbum-credits']/text()")
        release_date = dateparser.parse(re.sub(r'releas\w+ ', '', release_nodes[0].strip())) if release_nodes else None
        duration = None
        company = None
        brief_nodes = content.xpath("//div[@class='tralbumData tralbum-about']/text()")
        brief = "".join(brief_nodes) if brief_nodes else None
        cover_url = content.xpath("//div[@id='tralbumArt']/a/@href")[0].strip()
        bandcamp_page_data = json.loads(content.xpath(
            "//meta[@name='bc-page-properties']/@content")[0].strip())
        other_info = {}
        other_info['bandcamp_album_id'] = bandcamp_page_data['item_id']

        raw_img, ext = self.download_image(cover_url, url)

        data = {
            'title': title,
            'artist': artist,
            'genre': genre,
            'track_list': track_list,
            'release_date': release_date,
            'duration': duration,
            'company': company,
            'brief': brief,
            'other_info': other_info,
            'source_site': self.site_name,
            'source_url': effective_url,
            'cover_url': cover_url,
        }

        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img

    @classmethod
    def get_effective_url(cls, raw_url):
        url = cls.regex.findall(raw_url)
        return url[0] if len(url) > 0 else None
