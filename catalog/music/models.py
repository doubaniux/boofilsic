from catalog.common import *
from django.utils.translation import gettext_lazy as _
from django.db import models


class Album(Item):
    url_path = 'album'
    category = ItemCategory.Music
    demonstrative = _('这张专辑')
    barcode = PrimaryLookupIdDescriptor(IdType.GTIN)
    douban_music = PrimaryLookupIdDescriptor(IdType.DoubanMusic)
    spotify_album = PrimaryLookupIdDescriptor(IdType.Spotify_Album)
    METADATA_COPY_LIST = [
        'title',
        'other_title',
        'album_type',
        'media',
        'disc_count',
        'artist',
        'genre',
        'release_date',
        'duration',
        'company',
        'track_list',
        'brief',
    ]
    release_date = jsondata.DateField(_('发行日期'), auto_now=False, auto_now_add=False, null=True, blank=True)
    duration = jsondata.IntegerField(_("时长"), null=True, blank=True)
    artist = jsondata.ArrayField(models.CharField(_("artist"), blank=True, default='', max_length=200), null=True, blank=True, default=list)
    genre = jsondata.CharField(_("流派"), blank=True, default='', max_length=100)
    company = jsondata.ArrayField(models.CharField(blank=True, default='', max_length=500), null=True, blank=True, default=list)
    track_list = jsondata.TextField(_("曲目"), blank=True, default="")
    other_title = jsondata.CharField(blank=True, default='', max_length=500)
    album_type = jsondata.CharField(blank=True, default='', max_length=500)
    media = jsondata.CharField(blank=True, default='', max_length=500)
    disc_count = jsondata.IntegerField(blank=True, default='', max_length=500)
