import requests
import re
import time
from common.models import SourceSiteEnum
from music.models import Album, Song
from music.forms import AlbumForm, SongForm
from django.conf import settings
from common.scraper import *
from threading import Thread
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone


spotify_token = None
spotify_token_expire_time = time.time()


class SpotifyTrackScraper(AbstractScraper):
    site_name = SourceSiteEnum.SPOTIFY.value
    host = 'https://open.spotify.com/track/'
    data_class = Song
    form_class = SongForm

    regex = re.compile(r"(?<=https://open\.spotify\.com/track/)[a-zA-Z0-9]+")

    def scrape(self, url):
        """
        Request from API, not really scraping
        """
        global spotify_token, spotify_token_expire_time

        if spotify_token is None or is_spotify_token_expired():
            invoke_spotify_token()
        effective_url = self.get_effective_url(url)
        if effective_url is None:
            raise ValueError("not valid url")

        api_url = self.get_api_url(effective_url)
        headers = {
            'Authorization': f"Bearer {spotify_token}"
        }
        r = requests.get(api_url, headers=headers)
        res_data = r.json()

        artist = []
        for artist_dict in res_data['artists']:
            artist.append(artist_dict['name'])
        if not artist:
            artist = None

        title = res_data['name']

        release_date = parse_date(res_data['album']['release_date'])

        duration = res_data['duration_ms']

        if res_data['external_ids'].get('isrc'):
            isrc = res_data['external_ids']['isrc']
        else:
            isrc = None

        raw_img, ext = self.download_image(res_data['album']['images'][0]['url'], url)

        data = {
            'title': title,
            'artist': artist,
            'genre': None,
            'release_date': release_date,
            'duration': duration,
            'isrc': isrc,
            'album': None,
            'brief': None,
            'other_info': None,
            'source_site': self.site_name,
            'source_url': effective_url,
        }
        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img

    @classmethod
    def get_effective_url(cls, raw_url):
        code = cls.regex.findall(raw_url)
        if code:
            return f"https://open.spotify.com/track/{code[0]}"
        else:
            return None

    @classmethod
    def get_api_url(cls, url):
        return "https://api.spotify.com/v1/tracks/" + cls.regex.findall(url)[0]


class SpotifyAlbumScraper(AbstractScraper):
    site_name = SourceSiteEnum.SPOTIFY.value
    # API URL
    host = 'https://open.spotify.com/album/'
    data_class = Album
    form_class = AlbumForm

    regex = re.compile(r"(?<=https://open\.spotify\.com/album/)[a-zA-Z0-9]+")

    def scrape(self, url):
        """
        Request from API, not really scraping
        """
        global spotify_token, spotify_token_expire_time

        if spotify_token is None or is_spotify_token_expired():
            invoke_spotify_token()
        effective_url = self.get_effective_url(url)
        if effective_url is None:
            raise ValueError("not valid url")

        api_url = self.get_api_url(effective_url)
        headers = {
            'Authorization': f"Bearer {spotify_token}"
        }
        r = requests.get(api_url, headers=headers)
        res_data = r.json()

        artist = []
        for artist_dict in res_data['artists']:
            artist.append(artist_dict['name'])

        title = res_data['name']

        genre = ', '.join(res_data['genres'])

        company = []
        for com in res_data['copyrights']:
            company.append(com['text'])

        duration = 0
        track_list = []
        track_urls = []
        for track in res_data['tracks']['items']:
            track_urls.append(track['external_urls']['spotify'])
            duration += track['duration_ms']
            if res_data['tracks']['items'][-1]['disc_number'] > 1:
                # more than one disc
                track_list.append(str(
                    track['disc_number']) + '-' + str(track['track_number']) + '. ' + track['name'])
            else:
                track_list.append(str(track['track_number']) + '. ' + track['name'])
        track_list = '\n'.join(track_list)

        release_date = parse_date(res_data['release_date'])

        other_info = {}
        if res_data['external_ids'].get('upc'):
            # bar code
            other_info['UPC'] = res_data['external_ids']['upc']

        raw_img, ext = self.download_image(res_data['images'][0]['url'], url)

        data = {
            'title': title,
            'artist': artist,
            'genre': genre,
            'track_list': track_list,
            'release_date': release_date,
            'duration': duration,
            'company': company,
            'brief': None,
            'other_info': other_info,
            'source_site': self.site_name,
            'source_url': effective_url,
        }

        # set tracks_data, used for adding tracks
        self.track_urls = track_urls

        self.raw_data, self.raw_img, self.img_ext = data, raw_img, ext
        return data, raw_img

    @classmethod
    def get_effective_url(cls, raw_url):
        code = cls.regex.findall(raw_url)
        if code:
            return f"https://open.spotify.com/album/{code[0]}"
        else:
            return None

    # @classmethod
    # def save(cls, request_user):
    #     form = super().save(request_user)
    #     task = Thread(
    #         target=cls.add_tracks,
    #         args=(form.instance, request_user),
    #         daemon=True
    #     )
    #     task.start()
    #     return form

    @classmethod
    def get_api_url(cls, url):
        return "https://api.spotify.com/v1/albums/" + cls.regex.findall(url)[0]

    @classmethod
    def add_tracks(cls, album: Album, request_user):
        to_be_updated_tracks = []
        for track_url in cls.track_urls:
            track = cls.get_track_or_none(track_url)
            # seems lik if fire too many requests at the same time
            # spotify would limit access
            if track is None:
                task = Thread(
                    target=cls.scrape_and_save_track,
                    args=(track_url, album, request_user),
                    daemon=True
                )
                task.start()
                task.join()
            else:
                to_be_updated_tracks.append(track)
        cls.bulk_update_track_album(to_be_updated_tracks, album, request_user)

    @classmethod
    def get_track_or_none(cls, track_url: str):
        try:
            instance = Song.objects.get(source_url=track_url)
            return instance
        except ObjectDoesNotExist:
            return None

    @classmethod
    def scrape_and_save_track(cls, url: str, album: Album, request_user):
        data, img = SpotifyTrackScraper.scrape(url)
        SpotifyTrackScraper.raw_data['album'] = album
        SpotifyTrackScraper.save(request_user)

    @classmethod
    def bulk_update_track_album(cls, tracks, album, request_user):
        for track in tracks:
            track.last_editor = request_user
            track.edited_time = timezone.now()
            track.album = album
        Song.objects.bulk_update(tracks, [
            'last_editor',
            'edited_time',
            'album'
        ])


def get_spotify_token():
    global spotify_token, spotify_token_expire_time
    if spotify_token is None or is_spotify_token_expired():
        invoke_spotify_token()
    return spotify_token

    
def is_spotify_token_expired():
    global spotify_token_expire_time
    return True if spotify_token_expire_time <= time.time() else False


def invoke_spotify_token():
    global spotify_token, spotify_token_expire_time
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "client_credentials"
        },
        headers={
            "Authorization": f"Basic {settings.SPOTIFY_CREDENTIAL}"
        }
    )
    data = r.json()
    if r.status_code == 401:
        # token expired, try one more time
        # this maybe caused by external operations,
        # for example debugging using a http client
        r = requests.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "client_credentials"
            },
            headers={
                "Authorization": f"Basic {settings.SPOTIFY_CREDENTIAL}"
            }
        )
        data = r.json()
    elif r.status_code != 200:
        raise Exception(f"Request to spotify API fails. Reason: {r.reason}")
    # minus 2 for execution time error
    spotify_token_expire_time = int(data['expires_in']) + time.time() - 2
    spotify_token = data['access_token']
