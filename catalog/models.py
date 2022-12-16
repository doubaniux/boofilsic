from .common.models import Item
from .book.models import Edition, Work, Series
from .movie.models import Movie
from .tv.models import TVShow, TVSeason, TVEpisode
from .music.models import Album
from .game.models import Game
from .podcast.models import Podcast
from .performance.models import Performance
from .collection.models import Collection as CatalogCollection


# class Exhibition(Item):

#     class Meta:
#         proxy = True


# class Fanfic(Item):

#     class Meta:
#         proxy = True


# class Boardgame(Item):

#     class Meta:
#         proxy = True
