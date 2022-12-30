from catalog.common import *
from django.utils.translation import gettext_lazy as _
from django.db import models


class Game(Item):
    category = ItemCategory.Game
    url_path = "game"
    demonstrative = _("这个游戏")
    igdb = PrimaryLookupIdDescriptor(IdType.IGDB)
    steam = PrimaryLookupIdDescriptor(IdType.Steam)
    douban_game = PrimaryLookupIdDescriptor(IdType.DoubanGame)

    METADATA_COPY_LIST = [
        "title",
        "brief",
        "other_title",
        "developer",
        "publisher",
        "release_date",
        "genre",
        "platform",
        "official_site",
    ]

    other_title = jsondata.ArrayField(
        models.CharField(blank=True, default="", max_length=500),
        null=True,
        blank=True,
        default=list,
    )

    developer = jsondata.ArrayField(
        models.CharField(blank=True, default="", max_length=500),
        null=True,
        blank=True,
        default=list,
    )

    publisher = jsondata.ArrayField(
        models.CharField(blank=True, default="", max_length=500),
        null=True,
        blank=True,
        default=list,
    )

    release_date = jsondata.DateField(
        auto_now=False, auto_now_add=False, null=True, blank=True
    )

    genre = jsondata.ArrayField(
        models.CharField(blank=True, default="", max_length=200),
        null=True,
        blank=True,
        default=list,
    )

    platform = jsondata.ArrayField(
        models.CharField(blank=True, default="", max_length=200),
        null=True,
        blank=True,
        default=list,
    )

    official_site = jsondata.CharField(
        default="",
    )
