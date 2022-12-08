from catalog.common import *


class Game(Item):
    igdb = LookupIdDescriptor(IdType.IGDB)
    steam = LookupIdDescriptor(IdType.Steam)
    douban_game = LookupIdDescriptor(IdType.DoubanGame)
    platforms = jsondata.ArrayField(default=list)

    class Meta:
        proxy = True
