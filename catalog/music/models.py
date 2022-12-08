from catalog.common import *


class Album(Item):
    barcode = PrimaryLookupIdDescriptor(IdType.GTIN)
    douban_music = PrimaryLookupIdDescriptor(IdType.DoubanMusic)
    spotify_album = PrimaryLookupIdDescriptor(IdType.Spotify_Album)

    class Meta:
        proxy = True
