import re
from decimal import *
from markdown import markdown
from django.utils.translation import gettext_lazy as _
from django.db import models, IntegrityError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from markdownx.models import MarkdownxField
from users.models import User
from mastodon.api import get_relationships, get_cross_site_id
from django.utils import timezone
from django.conf import settings


RE_HTML_TAG = re.compile(r"<[^>]*>")


# abstract base classes
###################################
class SourceSiteEnum(models.TextChoices):
    IN_SITE = "in-site", settings.CLIENT_NAME
    DOUBAN = "douban", _("豆瓣")
    SPOTIFY = "spotify", _("Spotify")
    IMDB = "imdb", _("IMDb")
    STEAM = "steam", _("STEAM")
    BANGUMI = 'bangumi', _("bangumi")
    GOODREADS = "goodreads", _("goodreads")
    TMDB = "tmdb", _("The Movie Database")
    GOOGLEBOOKS = "googlebooks", _("Google Books")
    BANDCAMP = "bandcamp", _("BandCamp")


class Entity(models.Model):

    rating_total_score = models.PositiveIntegerField(null=True, blank=True)
    rating_number = models.PositiveIntegerField(null=True, blank=True)
    rating = models.DecimalField(
        null=True, blank=True, max_digits=3, decimal_places=1)
    created_time = models.DateTimeField(auto_now_add=True)
    edited_time = models.DateTimeField(auto_now=True)
    last_editor = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='%(class)s_last_editor', null=True, blank=False)
    brief = models.TextField(_("简介"), blank=True, default="")
    other_info = models.JSONField(_("其他信息"),
        blank=True, null=True, encoder=DjangoJSONEncoder, default=dict)
    # source_url should include shceme, which is normally https://
    source_url = models.URLField(_("URL"), max_length=500, unique=True)
    source_site = models.CharField(_("源网站"), choices=SourceSiteEnum.choices, max_length=50)

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(check=models.Q(
                rating__gte=0), name='%(class)s_rating_lowerbound'),
            models.CheckConstraint(check=models.Q(
                rating__lte=10), name='%(class)s_rating_upperbound'),
        ]


    def get_absolute_url(self):
        raise NotImplementedError("Subclass should implement this method")

    def save(self, *args, **kwargs):
        """ update rating and strip source url scheme & querystring before save to db """
        if self.rating_number and self.rating_total_score:
            self.rating = Decimal(
                str(round(self.rating_total_score / self.rating_number, 1)))
        elif self.rating_number is None and self.rating_total_score is None:
            self.rating = None
        else:
            raise IntegrityError()
        super().save(*args, **kwargs)

    def calculate_rating(self, old_rating, new_rating):
        if (not (self.rating and self.rating_total_score and self.rating_number)
                and (self.rating or self.rating_total_score or self.rating_number))\
                or (not (self.rating or self.rating_number or self.rating_total_score) and old_rating is not None):
            raise IntegrityError("Rating integiry error.")
        if old_rating:
            if new_rating:
                # old -> new
                self.rating_total_score += (new_rating - old_rating)
            else:
                # old -> none
                if self.rating_number >= 2:
                    self.rating_total_score -= old_rating
                    self.rating_number -= 1
                else:
                    # only one rating record
                    self.rating_number = None
                    self.rating_total_score = None
                pass
        else:
            if new_rating:
                # none -> new
                if self.rating_number and self.rating_number >= 1:
                    self.rating_total_score += new_rating
                    self.rating_number += 1
                else:
                    # no rating record before
                    self.rating_number = 1
                    self.rating_total_score = new_rating
            else:
                # none -> none
                pass

    def update_rating(self, old_rating, new_rating):
        """
        @param old_rating: the old mark rating
        @param new_rating: the new mark rating
        """
        self.calculate_rating(old_rating, new_rating)
        self.save()

    def get_tags_manager(self):
        """
        Since relation between tag and entity is foreign key, and related name has to be unique,
        this method works like interface.
        """
        raise NotImplementedError("Subclass should implement this method.")

    def get_marks_manager(self):
        """
        Normally this won't be used. 
        There is no ocassion where visitor can simply view all the marks.
        """
        raise NotImplementedError("Subclass should implement this method.")

    def get_reviews_manager(self):
        """
        Normally this won't be used.
        There is no ocassion where visitor can simply view all the reviews.
        """
        raise NotImplementedError("Subclass should implement this method.")

    @classmethod
    def get_category_mapping_dict(cls):
        category_mapping_dict = {}
        for subclass in cls.__subclasses__():
            category_mapping_dict[subclass.__name__.lower()] = subclass
        return category_mapping_dict

    @property
    def category_name(self):
        return self.__class__.__name__

    @property
    def verbose_category_name(self):
        raise NotImplementedError("Subclass should implement this.")


class UserOwnedEntity(models.Model):
    is_private = models.BooleanField(default=False, null=True)  # first set allow null, then migration, finally (in a few days) remove for good
    visibility = models.PositiveSmallIntegerField(default=0)  # 0: Public / 1: Follower only / 2: Self only
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='user_%(class)ss')
    created_time = models.DateTimeField(default=timezone.now)
    edited_time = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True

    def is_visible_to(self, viewer):
        if not viewer.is_authenticated:
            return self.visibility == 0
        owner = self.owner
        if owner == viewer:
            return True
        if self.visibility == 2:
            return False
        if viewer.is_blocking(owner) or owner.is_blocking(viewer) or viewer.is_muting(owner):
            return False
        if self.visibility == 1:
            return viewer.is_following(owner)
        else:
            return True

    @classmethod
    def get_available(cls, entity, request_user, following_only=False):
        # e.g. SongMark.get_available(song, request.user, request.session['oauth_token'])
        query_kwargs = {entity.__class__.__name__.lower(): entity}
        all_entities = cls.objects.filter(**query_kwargs).order_by("-edited_time")  # get all marks for song
        visible_entities = list(filter(lambda _entity: _entity.is_visible_to(request_user) and (_entity.owner.mastodon_username in request_user.mastodon_following if following_only else True), all_entities))
        return visible_entities

    @classmethod
    def get_available_by_user(cls, owner, is_following):  # FIXME
        """ 
        Returns all avaliable owner's entities.
        Mute/Block relation is not handled in this method.

        :param owner: visited user
        :param is_following: if the current user is following the owner
        """
        user_owned_entities = cls.objects.filter(owner=owner)
        if not is_following:
            user_owned_entities = user_owned_entities.exclude(visibility__gt=0)
        return user_owned_entities


# commonly used entity classes
###################################
class MarkStatusEnum(models.TextChoices):
    WISH = 'wish', _('Wish')
    DO = 'do', _('Do')
    COLLECT = 'collect', _('Collect')


class Mark(UserOwnedEntity):
    status = models.CharField(choices=MarkStatusEnum.choices, max_length=20)
    rating = models.PositiveSmallIntegerField(blank=True, null=True)
    text = models.CharField(max_length=5000, blank=True, default='')

    def __str__(self):
        return f"Mark({self.id} {self.owner} {self.status.upper()})"

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(check=models.Q(
                rating__gte=0), name='mark_rating_lowerbound'),
            models.CheckConstraint(check=models.Q(
                rating__lte=10), name='mark_rating_upperbound'),
        ]
    
    # TODO update entity rating when save
    # TODO update tags


class Review(UserOwnedEntity):
    title = models.CharField(max_length=120)
    content = MarkdownxField()

    def __str__(self):
        return self.title

    def get_plain_content(self):
        """
        Get plain text format content
        """
        html = markdown(self.content)
        return RE_HTML_TAG.sub(' ', html)

    class Meta:
        abstract = True


class Tag(models.Model):
    content = models.CharField(max_length=50)

    def __str__(self):
        return self.content

    class Meta:
        abstract = True
