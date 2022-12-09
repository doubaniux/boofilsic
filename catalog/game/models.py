from catalog.common import *


class Game(Item):
    igdb = PrimaryLookupIdDescriptor(IdType.IGDB)
    steam = PrimaryLookupIdDescriptor(IdType.Steam)
    douban_game = PrimaryLookupIdDescriptor(IdType.DoubanGame)
    platforms = jsondata.ArrayField(default=list)
