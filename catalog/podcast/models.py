from catalog.common import *
from django.db import models
from django.utils.translation import gettext_lazy as _


class Podcast(Item):
    category = ItemCategory.Podcast
    url_path = "podcast"
    demonstrative = _("这个播客")
    feed_url = PrimaryLookupIdDescriptor(IdType.Feed)
    apple_podcast = PrimaryLookupIdDescriptor(IdType.ApplePodcast)
    # ximalaya = LookupIdDescriptor(IdType.Ximalaya)
    # xiaoyuzhou = LookupIdDescriptor(IdType.Xiaoyuzhou)
    hosts = jsondata.ArrayField(models.CharField(), default=list)


# class PodcastEpisode(Item):
#     pass
