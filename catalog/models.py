from .common.models import Item
from .book.models import Edition, Work, Series
from .movie.models import Movie
from .tv.models import TVShow, TVSeason, TVEpisode
from .music.models import Album
from .game.models import Game
from .podcast.models import Podcast
from .performance.models import Performance
from .collection.models import Collection as CatalogCollection
from django.contrib.contenttypes.models import ContentType


# class Exhibition(Item):

#     class Meta:
#         proxy = True


# class Fanfic(Item):

#     class Meta:
#         proxy = True


# class Boardgame(Item):

#     class Meta:
#         proxy = True


CATEGORY_LIST = {}
CONTENT_TYPE_LIST = {}


def _init_item_subclasses():
    for cls in Item.__subclasses__():
        c = getattr(cls, 'category', None)
        if c not in CATEGORY_LIST:
            CATEGORY_LIST[c] = [cls]
        else:
            CATEGORY_LIST[c].append(cls)
        CONTENT_TYPE_LIST[cls] = ContentType.objects.get(app_label='catalog', model=cls.__name__.lower()).id


_init_item_subclasses()
