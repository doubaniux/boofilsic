from catalog.common import *


class Movie(Item):
    category = ItemCategory.Movie
    imdb = PrimaryLookupIdDescriptor(IdType.IMDB)
    tmdb_movie = PrimaryLookupIdDescriptor(IdType.TMDB_Movie)
    douban_movie = PrimaryLookupIdDescriptor(IdType.DoubanMovie)
    duration = jsondata.IntegerField(blank=True, default=None)
