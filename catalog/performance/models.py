from catalog.common import *
from django.utils.translation import gettext_lazy as _
from django.db import models


class Performance(Item):
    category = ItemCategory.Performance
    url_path = "performance"
    douban_drama = LookupIdDescriptor(IdType.DoubanDrama)
    versions = jsondata.ArrayField(
        verbose_name=_("版本"),
        base_field=models.CharField(),
        null=False,
        blank=False,
        default=list,
    )
    directors = jsondata.ArrayField(
        verbose_name=_("导演"),
        base_field=models.CharField(),
        null=False,
        blank=False,
        default=list,
    )
    playwrights = jsondata.ArrayField(
        verbose_name=_("编剧"),
        base_field=models.CharField(),
        null=False,
        blank=False,
        default=list,
    )
    actors = jsondata.ArrayField(
        verbose_name=_("主演"),
        base_field=models.CharField(),
        null=False,
        blank=False,
        default=list,
    )

    class Meta:
        proxy = True
