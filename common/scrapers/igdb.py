import requests
import re
from common.models import SourceSiteEnum
from games.models import Game
from games.forms import GameForm
from django.conf import settings
from common.scraper import *
from igdb.wrapper import IGDBWrapper
import json
import datetime


wrapper = IGDBWrapper(settings.IGDB_CLIENT_ID, settings.IGDB_ACCESS_TOKEN)


class IgdbGameScraper(AbstractScraper):
    site_name = SourceSiteEnum.IGDB.value
    host = 'https://www.igdb.com/'
    data_class = Game
    form_class = GameForm
    regex = re.compile(r"https://www\.igdb\.com/games/([a-zA-Z0-9\-_]+)")

    def scrape(self, url):
        m = self.regex.match(url)
        if m:
            effective_url = m[0]
        else:
            raise ValueError("not valid url")
        effective_url = m[0]
        slug = m[1]
        fields = '*, cover.url, genres.name, platforms.name, involved_companies.*, involved_companies.company.name'
        r = json.loads(wrapper.api_request('games', f'fields {fields}; where url = "{effective_url}";'))[0]
        raw_img, ext = self.download_image('https:' + r['cover']['url'].replace('t_thumb', 't_cover_big'), url)
        developer = None
        publisher = None
        release_date = None
        genre = None
        platform = None
        if 'involved_companies' in r:
            developer = next(iter([c['company']['name'] for c in r['involved_companies'] if c['developer'] == True]), None)
            publisher = next(iter([c['company']['name'] for c in r['involved_companies'] if c['publisher'] == True]), None)
        if 'platforms' in r:
            platform = [p['name'] for p in r['platforms']]
        if 'first_release_date' in r:
            release_date = datetime.datetime.fromtimestamp(r['first_release_date'], datetime.timezone.utc)
        if 'genres' in r:
            genre = [g['name'] for g in r['genres']]
        other_info = {'igdb_id': r['id']}
        websites = json.loads(wrapper.api_request('websites', f'fields *; where game.url = "{effective_url}";'))
        for website in websites:
            if website['category'] == 1:
                other_info['official_site'] = website['url']
            elif website['category'] == 13:
                other_info['steam_url'] = website['url']
        data = {
            'title': r['name'],
            'other_title': None,
            'developer': developer,
            'publisher': publisher,
            'release_date': release_date,
            'genre': genre,
            'platform': platform,
            'brief': r['storyline'],
            'other_info': other_info,
            'source_site': self.site_name,
            'source_url': self.get_effective_url(url),
        }

        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img

    @classmethod
    def get_effective_url(cls, raw_url):
        m = cls.regex.match(raw_url)
        if raw_url:
            return m[0]
        else:
            return None
