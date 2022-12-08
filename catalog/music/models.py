from catalog.common import *


class Album(Item):
    upc = LookupIdDescriptor(IdType.UPC)
    douban_music = LookupIdDescriptor(IdType.DoubanMusic)
    spotify_album = LookupIdDescriptor(IdType.Spotify_Album)

    class Meta:
        proxy = True
