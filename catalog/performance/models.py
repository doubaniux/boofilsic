from catalog.common import *
from django.utils.translation import gettext_lazy as _


class Performance(Item):
    category = ItemCategory.Performance
    url_path = "performance"
    douban_drama = LookupIdDescriptor(IdType.DoubanDrama)
    versions = jsondata.ArrayField(_("版本"), null=False, blank=False, default=list)
    directors = jsondata.ArrayField(_("导演"), null=False, blank=False, default=list)
    playwrights = jsondata.ArrayField(_("编剧"), null=False, blank=False, default=list)
    actors = jsondata.ArrayField(_("主演"), null=False, blank=False, default=list)

    class Meta:
        proxy = True
