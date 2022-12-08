"""
Models for TV

TVShow -> TVSeason -> TVEpisode

TVEpisode is not fully implemented at the moment

Three way linking between Douban / IMDB / TMDB are quite messy

IMDB:
most widely used. 
no ID for Season, only for Show and Episode

TMDB:
most friendly API.
for some TV specials, both shown as an Episode of Season 0 and a Movie, with same IMDB id

Douban:
most wanted by our users.
for single season show, IMDB id of the show id used
for multi season show, IMDB id for Ep 1 will be used to repensent that season
tv specials are are shown as movies

For now, we follow Douban convention, but keep an eye on it in case it breaks its own rules...

"""
from catalog.common import *
from django.db import models


class TVShow(Item):
    imdb = PrimaryLookupIdDescriptor(IdType.IMDB)
    tmdb_tv = PrimaryLookupIdDescriptor(IdType.TMDB_TV)
    imdb = PrimaryLookupIdDescriptor(IdType.IMDB)
    season_count = jsondata.IntegerField(blank=True, default=None)


class TVSeason(Item):
    douban_movie = PrimaryLookupIdDescriptor(IdType.DoubanMovie)
    imdb = PrimaryLookupIdDescriptor(IdType.IMDB)
    tmdb_tvseason = PrimaryLookupIdDescriptor(IdType.TMDB_TVSeason)
    series = models.ForeignKey(TVShow, null=True, on_delete=models.SET_NULL, related_name='seasons')
    season_number = models.PositiveIntegerField()
    episode_count = jsondata.IntegerField(blank=True, default=None)
    METADATA_COPY_LIST = ['title', 'brief', 'season_number', 'episode_count']


class TVEpisode(Item):
    series = models.ForeignKey(TVShow, null=True, on_delete=models.SET_NULL, related_name='episodes')
    season = models.ForeignKey(TVSeason, null=True, on_delete=models.SET_NULL, related_name='episodes')
    episode_number = models.PositiveIntegerField()
    imdb = PrimaryLookupIdDescriptor(IdType.IMDB)
    METADATA_COPY_LIST = ['title', 'brief', 'episode_number']
