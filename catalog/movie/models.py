from catalog.common import *
from django.utils.translation import gettext_lazy as _
from django.db import models


class Movie(Item):
    category = ItemCategory.Movie
    url_path = 'movie'
    imdb = PrimaryLookupIdDescriptor(IdType.IMDB)
    tmdb_movie = PrimaryLookupIdDescriptor(IdType.TMDB_Movie)
    douban_movie = PrimaryLookupIdDescriptor(IdType.DoubanMovie)
    demonstrative = _('这部电影')

    METADATA_COPY_LIST = [
        'title',
        'orig_title',
        'other_title',
        'director',
        'playwright',
        'actor',
        'genre',
        'showtime',
        'site',
        'area',
        'language',
        'year',
        'duration',
        'season_number',
        'episodes',
        'single_episode_length',
        'brief',
    ]
    orig_title = jsondata.CharField(_("original title"), blank=True, default='', max_length=500)
    other_title = jsondata.ArrayField(models.CharField(_("other title"), blank=True, default='', max_length=500), null=True, blank=True, default=list, )
    director = jsondata.ArrayField(models.CharField(_("director"), blank=True, default='', max_length=200), null=True, blank=True, default=list, )
    playwright = jsondata.ArrayField(models.CharField(_("playwright"), blank=True, default='', max_length=200), null=True, blank=True, default=list, )
    actor = jsondata.ArrayField(models.CharField(_("actor"), blank=True, default='', max_length=200), null=True, blank=True, default=list, )
    genre = jsondata.ArrayField(models.CharField(_("genre"), blank=True, default='', max_length=50), null=True, blank=True, default=list, )  # , choices=MovieGenreEnum.choices
    showtime = jsondata.ArrayField(null=True, blank=True, default=list, )
    site = jsondata.URLField(_('site url'), blank=True, default='', max_length=200)
    area = jsondata.ArrayField(models.CharField(_("country or region"), blank=True, default='', max_length=100, ), null=True, blank=True, default=list, )
    language = jsondata.ArrayField(models.CharField(blank=True, default='', max_length=100, ), null=True, blank=True, default=list, )
    year = jsondata.IntegerField(null=True, blank=True)
    season_number = jsondata.IntegerField(null=True, blank=True)
    episodes = jsondata.IntegerField(null=True, blank=True)
    single_episode_length = jsondata.IntegerField(null=True, blank=True)
    duration = jsondata.CharField(blank=True, default='', max_length=200)
