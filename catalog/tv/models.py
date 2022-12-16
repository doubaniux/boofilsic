"""
Models for TV

TVShow -> TVSeason -> TVEpisode

TVEpisode is not fully implemented at the moment

Three way linking between Douban / IMDB / TMDB are quite messy

IMDB:
most widely used. 
no ID for Season, only for Show and Episode

TMDB:
most friendly API.
for some TV specials, both shown as an Episode of Season 0 and a Movie, with same IMDB id

Douban:
most wanted by our users.
for single season show, IMDB id of the show id used
for multi season show, IMDB id for Ep 1 will be used to repensent that season
tv specials are are shown as movies

For now, we follow Douban convention, but keep an eye on it in case it breaks its own rules...

"""
from catalog.common import *
from django.db import models
from django.utils.translation import gettext_lazy as _


class TVShow(Item):
    category = ItemCategory.TV
    url_path = 'tv'
    demonstrative = _('这部剧集')
    imdb = PrimaryLookupIdDescriptor(IdType.IMDB)
    tmdb_tv = PrimaryLookupIdDescriptor(IdType.TMDB_TV)
    imdb = PrimaryLookupIdDescriptor(IdType.IMDB)
    season_count = jsondata.IntegerField(null=True)

    METADATA_COPY_LIST = [
        'title',
        'season_count',
        'orig_title',
        'other_title',
        'director',
        'playwright',
        'actor',
        'genre',
        'showtime',
        'site',
        'area',
        'language',
        'year',
        'duration',
        'season_number',
        'single_episode_length',
        'brief',
    ]
    orig_title = jsondata.CharField(_("original title"), blank=True, default='', max_length=500)
    other_title = jsondata.ArrayField(models.CharField(_("other title"), blank=True, default='', max_length=500), null=True, blank=True, default=list, )
    director = jsondata.ArrayField(models.CharField(_("director"), blank=True, default='', max_length=200), null=True, blank=True, default=list, )
    playwright = jsondata.ArrayField(models.CharField(_("playwright"), blank=True, default='', max_length=200), null=True, blank=True, default=list, )
    actor = jsondata.ArrayField(models.CharField(_("actor"), blank=True, default='', max_length=200), null=True, blank=True, default=list, )
    genre = jsondata.ArrayField(models.CharField(_("genre"), blank=True, default='', max_length=50), null=True, blank=True, default=list, )  # , choices=MovieGenreEnum.choices
    showtime = jsondata.ArrayField(null=True, blank=True, default=list, )
    site = jsondata.URLField(_('site url'), blank=True, default='', max_length=200)
    area = jsondata.ArrayField(models.CharField(_("country or region"), blank=True, default='', max_length=100, ), null=True, blank=True, default=list, )
    language = jsondata.ArrayField(models.CharField(blank=True, default='', max_length=100, ), null=True, blank=True, default=list, )
    year = jsondata.IntegerField(null=True, blank=True)
    season_number = jsondata.IntegerField(null=True, blank=True)
    single_episode_length = jsondata.IntegerField(null=True, blank=True)
    duration = jsondata.CharField(blank=True, default='', max_length=200)


class TVSeason(Item):
    category = ItemCategory.TV
    url_path = 'tv/season'
    demonstrative = _('这部剧集')
    douban_movie = PrimaryLookupIdDescriptor(IdType.DoubanMovie)
    imdb = PrimaryLookupIdDescriptor(IdType.IMDB)
    tmdb_tvseason = PrimaryLookupIdDescriptor(IdType.TMDB_TVSeason)
    show = models.ForeignKey(TVShow, null=True, on_delete=models.SET_NULL, related_name='seasons')
    season_number = models.PositiveIntegerField(null=True)
    episode_count = models.PositiveIntegerField(null=True)

    METADATA_COPY_LIST = [
        'title',
        'orig_title',
        'other_title',
        'director',
        'playwright',
        'actor',
        'genre',
        'showtime',
        'site',
        'area',
        'language',
        'year',
        'duration',
        'season_number',
        'episode_count',
        'single_episode_length',
        'brief',
    ]
    orig_title = jsondata.CharField(_("original title"), blank=True, default='', max_length=500)
    other_title = jsondata.ArrayField(models.CharField(_("other title"), blank=True, default='', max_length=500), null=True, blank=True, default=list, )
    director = jsondata.ArrayField(models.CharField(_("director"), blank=True, default='', max_length=200), null=True, blank=True, default=list, )
    playwright = jsondata.ArrayField(models.CharField(_("playwright"), blank=True, default='', max_length=200), null=True, blank=True, default=list, )
    actor = jsondata.ArrayField(models.CharField(_("actor"), blank=True, default='', max_length=200), null=True, blank=True, default=list, )
    genre = jsondata.ArrayField(models.CharField(_("genre"), blank=True, default='', max_length=50), null=True, blank=True, default=list, )  # , choices=MovieGenreEnum.choices
    showtime = jsondata.ArrayField(null=True, blank=True, default=list, )
    site = jsondata.URLField(_('site url'), blank=True, default='', max_length=200)
    area = jsondata.ArrayField(models.CharField(_("country or region"), blank=True, default='', max_length=100, ), null=True, blank=True, default=list, )
    language = jsondata.ArrayField(models.CharField(blank=True, default='', max_length=100, ), null=True, blank=True, default=list, )
    year = jsondata.IntegerField(null=True, blank=True)
    single_episode_length = jsondata.IntegerField(null=True, blank=True)
    duration = jsondata.CharField(blank=True, default='', max_length=200)

    def update_linked_items_from_external_resource(self, resource):
        """add Work from resource.metadata['work'] if not yet"""
        links = resource.required_resources + resource.related_resources
        for w in links:
            if w['model'] == 'TVShow':
                p = ExternalResource.objects.filter(id_type=w['id_type'], id_value=w['id_value']).first()
                if p and p.item and self.show != p.item:
                    self.show = p.item


class TVEpisode(Item):
    category = ItemCategory.TV
    url_path = 'tv/episode'
    show = models.ForeignKey(TVShow, null=True, on_delete=models.SET_NULL, related_name='episodes')
    season = models.ForeignKey(TVSeason, null=True, on_delete=models.SET_NULL, related_name='episodes')
    episode_number = models.PositiveIntegerField(null=True)
    imdb = PrimaryLookupIdDescriptor(IdType.IMDB)
    METADATA_COPY_LIST = ['title', 'brief', 'episode_number']
