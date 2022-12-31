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
from django.conf import settings


if settings.SEARCH_BACKEND == "MEILISEARCH":
    from .search.meilisearch import Indexer
elif settings.SEARCH_BACKEND == "TYPESENSE":
    from .search.typesense import Indexer
else:

    class Indexer:
        @classmethod
        def update_model_indexable(cls, model):
            pass


# class Exhibition(Item):

#     class Meta:
#         proxy = True


# class Fanfic(Item):

#     class Meta:
#         proxy = True


# class Boardgame(Item):

#     class Meta:
#         proxy = True


_CATEGORY_LIST = None
_CONTENT_TYPE_LIST = None


def all_content_types():
    global _CONTENT_TYPE_LIST
    if _CONTENT_TYPE_LIST is None:
        _CONTENT_TYPE_LIST = {}
        for cls in Item.__subclasses__():
            _CONTENT_TYPE_LIST[cls] = ContentType.objects.get(
                app_label="catalog", model=cls.__name__.lower()
            ).id
    return _CONTENT_TYPE_LIST


def all_categories():
    global _CATEGORY_LIST
    if _CATEGORY_LIST is None:
        _CATEGORY_LIST = {}
        for cls in Item.__subclasses__():
            c = getattr(cls, "category", None)
            if c not in _CATEGORY_LIST:
                _CATEGORY_LIST[c] = [cls]
            else:
                _CATEGORY_LIST[c].append(cls)
    return _CATEGORY_LIST


def init_catalog_search_models():
    Indexer.update_model_indexable(Edition)
    Indexer.update_model_indexable(Work)
    Indexer.update_model_indexable(Movie)
    Indexer.update_model_indexable(TVShow)
    Indexer.update_model_indexable(TVSeason)
    Indexer.update_model_indexable(Album)
    Indexer.update_model_indexable(Game)
