import requests
import re
from common.models import SourceSiteEnum
from movies.models import Movie
from movies.forms import MovieForm
from django.conf import settings
from common.scraper import *


class TmdbMovieScraper(AbstractScraper):
    site_name = SourceSiteEnum.TMDB.value
    host = 'https://www.themoviedb.org/'
    data_class = Movie
    form_class = MovieForm
    regex = re.compile(r"https://www\.themoviedb\.org/(movie|tv)/([a-zA-Z0-9]+)")
    # http://api.themoviedb.org/3/genre/movie/list?api_key=&language=zh
    # http://api.themoviedb.org/3/genre/tv/list?api_key=&language=zh
    genre_map = {
        'Sci-Fi & Fantasy': 'Sci-Fi',
        'War & Politics':   'War',
        '儿童':             'Kids',
        '冒险':             'Adventure',
        '剧情':             'Drama',
        '动作':             'Action',
        '动作冒险':         'Action',
        '动画':             'Animation',
        '历史':             'History',
        '喜剧':             'Comedy',
        '奇幻':             'Fantasy',
        '家庭':             'Family',
        '恐怖':             'Horror',
        '悬疑':             'Mystery',
        '惊悚':             'Thriller',
        '战争':             'War',
        '新闻':             'News',
        '爱情':             'Romance',
        '犯罪':             'Crime',
        '电视电影':         'TV Movie',
        '真人秀':           'Reality-TV',
        '科幻':             'Sci-Fi',
        '纪录':             'Documentary',
        '肥皂剧':           'Soap',
        '脱口秀':           'Talk-Show',
        '西部':             'Western',
        '音乐':             'Music',
    }

    def scrape_imdb(self, imdb_code):
        api_url = f"https://api.themoviedb.org/3/find/{imdb_code}?api_key={settings.TMDB_API3_KEY}&language=zh-CN&external_source=imdb_id"
        r = requests.get(api_url)
        res_data = r.json()
        if 'movie_results' in res_data and len(res_data['movie_results']) > 0:
            url = f"https://www.themoviedb.org/movie/{res_data['movie_results'][0]['id']}"
        elif 'tv_results' in res_data and len(res_data['tv_results']) > 0:
            url = f"https://www.themoviedb.org/tv/{res_data['tv_results'][0]['id']}"
        else:
            raise ValueError("Cannot find IMDb ID in TMDB")
        return self.scrape(url)

    def scrape(self, url):
        m = self.regex.match(url)
        if m:
            effective_url = m[0]
        else:
            raise ValueError("not valid url")
        effective_url = m[0]
        is_series = m[1] == 'tv'
        id = m[2]
        if is_series:
            api_url = f"https://api.themoviedb.org/3/tv/{id}?api_key={settings.TMDB_API3_KEY}&language=zh-CN&append_to_response=external_ids,credits"
        else:
            api_url = f"https://api.themoviedb.org/3/movie/{id}?api_key={settings.TMDB_API3_KEY}&language=zh-CN&append_to_response=external_ids,credits"
        r = requests.get(api_url)
        res_data = r.json()

        if is_series:
            title = res_data['name']
            orig_title = res_data['original_name']
            year = int(res_data['first_air_date'].split('-')[0]) if res_data['first_air_date'] else None
            imdb_code = res_data['external_ids']['imdb_id']
            showtime = [{res_data['first_air_date']: "首播日期"}] if res_data['first_air_date'] else None
            duration = None
        else:
            title = res_data['title']
            orig_title = res_data['original_title']
            year = int(res_data['release_date'].split('-')[0]) if res_data['release_date'] else None
            showtime = [{res_data['release_date']: "发布日期"}] if res_data['release_date'] else None
            imdb_code = res_data['imdb_id']
            duration = res_data['runtime'] if res_data['runtime'] else None # in minutes

        genre = list(map(lambda x: self.genre_map[x['name']] if x['name'] in self.genre_map else 'Other', res_data['genres']))
        language = list(map(lambda x: x['name'], res_data['spoken_languages']))
        brief = res_data['overview']

        if is_series:
            director = list(map(lambda x: x['name'], res_data['created_by']))
        else:
            director = list(map(lambda x: x['name'], filter(lambda c: c['job'] == 'Director', res_data['credits']['crew'])))
        playwright = list(map(lambda x: x['name'], filter(lambda c: c['job'] == 'Screenplay', res_data['credits']['crew'])))
        actor = list(map(lambda x: x['name'], res_data['credits']['cast']))
        area = []

        other_info = {}
        other_info['TMDB评分'] = res_data['vote_average']
        # other_info['分级'] = res_data['contentRating']
        # other_info['Metacritic评分'] = res_data['metacriticRating']
        # other_info['奖项'] = res_data['awards']
        other_info['TMDB_ID'] = id
        if is_series:
            other_info['Seasons'] = res_data['number_of_seasons']
            other_info['Episodes'] = res_data['number_of_episodes']

        img_url = ('https://image.tmdb.org/t/p/original/' + res_data['poster_path']) if res_data['poster_path'] is not None else None
        # TODO: use GET /configuration to get base url
        raw_img, ext = self.download_image(img_url, url)

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
        m = cls.regex.match(raw_url)
        if raw_url:
            return m[0]
        else:
            return None
