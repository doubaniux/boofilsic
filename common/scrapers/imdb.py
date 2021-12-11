import requests
import re
from common.models import SourceSiteEnum
from movies.forms import MovieForm
from movies.models import Movie
from django.conf import settings
from common.scraper import *


class ImdbMovieScraper(AbstractScraper):
    site_name = SourceSiteEnum.IMDB.value
    host = 'https://www.imdb.com/title/'
    data_class = Movie
    form_class = MovieForm

    regex = re.compile(r"(?<=https://www\.imdb\.com/title/)[a-zA-Z0-9]+")

    def scrape(self, url):

        effective_url = self.get_effective_url(url)
        if effective_url is None:
            raise ValueError("not valid url")

        api_url = self.get_api_url(effective_url)
        r = requests.get(api_url)
        res_data = r.json()

        if not res_data['type'] in ['Movie', 'TVSeries']:
            raise ValueError("not movie/series item")

        if res_data['type'] == 'Movie':
            is_series = False
        elif res_data['type'] == 'TVSeries':
            is_series = True

        title = res_data['title']
        orig_title = res_data['originalTitle']
        imdb_code = self.regex.findall(effective_url)[0]
        director = []
        for direct_dict in res_data['directorList']:
            director.append(direct_dict['name'])
        playwright = []
        for writer_dict in res_data['writerList']:
            playwright.append(writer_dict['name'])
        actor = []
        for actor_dict in res_data['actorList']:
            actor.append(actor_dict['name'])
        genre = res_data['genres'].split(', ')
        area = res_data['countries'].split(', ')
        language = res_data['languages'].split(', ')
        year = int(res_data['year'])
        duration = res_data['runtimeStr']
        brief = res_data['plotLocal'] if res_data['plotLocal'] else res_data['plot']
        if res_data['releaseDate']:
            showtime = [{res_data['releaseDate']: "发布日期"}]
        else:
            showtime = None

        other_info = {}
        if res_data['contentRating']:
            other_info['分级'] = res_data['contentRating']
        if res_data['imDbRating']:
            other_info['IMDb评分'] = res_data['imDbRating']
        if res_data['metacriticRating']:
            other_info['Metacritic评分'] = res_data['metacriticRating']
        if res_data['awards']:
            other_info['奖项'] = res_data['awards']

        raw_img, ext = self.download_image(res_data['image'], url)

        data = {
            'title': title,
            'orig_title': orig_title,
            'other_title': None,
            'imdb_code': imdb_code,
            'director': director,
            'playwright': playwright,
            'actor': actor,
            'genre': genre,
            'showtime': showtime,
            'site': None,
            'area': area,
            'language': language,
            'year': year,
            'duration': duration,
            'season': None,
            'episodes': None,
            'single_episode_length': None,
            'brief': brief,
            'is_series': is_series,
            'other_info': other_info,
            'source_site': self.site_name,
            'source_url': effective_url,
        }
        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img

    @classmethod
    def get_effective_url(cls, raw_url):
        code = cls.regex.findall(raw_url)
        if code:
            return f"https://www.imdb.com/title/{code[0]}/"
        else:
            return None

    @classmethod
    def get_api_url(cls, url):
        return f"https://imdb-api.com/zh/API/Title/{settings.IMDB_API_KEY}/{cls.regex.findall(url)[0]}/FullActor,"
