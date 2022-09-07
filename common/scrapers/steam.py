import re
from common.models import SourceSiteEnum
from games.models import Game
from games.forms import GameForm
from common.scraper import *
from common.scrapers.igdb import IgdbGameScraper


class SteamGameScraper(AbstractScraper):
    site_name = SourceSiteEnum.STEAM.value
    host = 'store.steampowered.com'
    data_class = Game
    form_class = GameForm

    regex = re.compile(r"https://store\.steampowered\.com/app/\d+")

    def scrape(self, url):
        m = self.regex.match(url)
        if m:
            effective_url = m[0]
        else:
            raise ValueError("not valid url")
        s = IgdbGameScraper()
        s.scrape_steam(effective_url)
        self.raw_data = s.raw_data
        self.raw_img = s.raw_img
        self.img_ext = s.img_ext
        self.raw_data['source_site'] = self.site_name
        self.raw_data['source_url'] = effective_url
        return self.raw_data, self.raw_img
        headers = DEFAULT_REQUEST_HEADERS.copy()
        headers['Host'] = self.host
        headers['Cookie'] = "wants_mature_content=1; birthtime=754700401;"
        content = self.download_page(url, headers)

        title = content.xpath("//div[@class='apphub_AppName']/text()")[0]
        developer = content.xpath("//div[@id='developers_list']/a/text()")
        publisher = content.xpath("//div[@class='glance_ctn']//div[@class='dev_row'][2]//a/text()")
        release_date = parse_date(
            content.xpath(
                "//div[@class='release_date']/div[@class='date']/text()")[0]
        )

        genre = content.xpath(
            "//div[@class='details_block']/b[2]/following-sibling::a/text()")

        platform = ['PC']

        brief = content.xpath(
            "//div[@class='game_description_snippet']/text()")[0].strip()

        img_url = content.xpath(
            "//img[@class='game_header_image_full']/@src"
        )[0].replace("header.jpg", "library_600x900.jpg")
        raw_img, ext = self.download_image(img_url, url)

        # no 600x900 picture
        if raw_img is None:
            img_url = content.xpath("//img[@class='game_header_image_full']/@src")[0]
            raw_img, ext = self.download_image(img_url, url)

        data = {
            'title': title,
            'other_title': None,
            'developer': developer,
            'publisher': publisher,
            'release_date': release_date,
            'genre': genre,
            'platform': platform,
            'brief': brief,
            'other_info': None,
            'source_site': self.site_name,
            'source_url': effective_url
        }

        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img

    @classmethod
    def get_effective_url(cls, raw_url):
        m = cls.regex.match(raw_url)
        if m:
            return m[0]
        else:
            return None
