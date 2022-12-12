from catalog.common import *


class Podcast(Item):
    category = ItemCategory.Podcast
    url_path = 'podcast'
    feed_url = PrimaryLookupIdDescriptor(IdType.Feed)
    apple_podcast = PrimaryLookupIdDescriptor(IdType.ApplePodcast)
    # ximalaya = LookupIdDescriptor(IdType.Ximalaya)
    # xiaoyuzhou = LookupIdDescriptor(IdType.Xiaoyuzhou)
    hosts = jsondata.ArrayField(default=list)


# class PodcastEpisode(Item):
#     pass
