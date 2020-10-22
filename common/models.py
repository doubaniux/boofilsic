import django.contrib.postgres.fields as postgres
from decimal import *
from django.utils.translation import ugettext_lazy as _
from django.db import models, IntegrityError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from markdownx.models import MarkdownxField
from users.models import User
from mastodon.api import get_relationships, get_cross_site_id


# abstract base classes
###################################
class Resource(models.Model):

    rating_total_score = models.PositiveIntegerField(null=True, blank=True)
    rating_number = models.PositiveIntegerField(null=True, blank=True)
    rating = models.DecimalField(
        null=True, blank=True, max_digits=3, decimal_places=1)
    created_time = models.DateTimeField(auto_now_add=True)
    edited_time = models.DateTimeField(auto_now_add=True)
    last_editor = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='%(class)s_last_editor', null=True, blank=False)
    brief = models.TextField(blank=True, default="")
    other_info = postgres.JSONField(
        blank=True, null=True, encoder=DjangoJSONEncoder, default=dict)

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(check=models.Q(
                rating__gte=0), name='%(class)s_rating_lowerbound'),
            models.CheckConstraint(check=models.Q(
                rating__lte=10), name='%(class)s_rating_upperbound'),
        ]

    def save(self, *args, **kwargs):
        """ update rating before save to db """
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
        self.calculate_rating(old_rating, new_rating)
        self.save()

    def get_tags_manager(self):
        """
        Since relation between tag and resource is foreign key, and related name has to be unique,
        this method works like interface.
        """
        raise NotImplementedError("Subclass should implement this method.")

    def get_marks_manager(self):
        """
        Normally this won't be used. 
        There is no ocassion where visitor can simply view all the marks.
        """
        raise NotImplementedError("Subclass should implement this method.")

    def get_revies_manager(self):
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
    is_private = models.BooleanField()
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='user_%(class)ss')
    created_time = models.DateTimeField(auto_now_add=True)
    edited_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    @classmethod
    def get_available(cls, resource, request_user, token):
        # TODO add amount limit for once query
        """ 
        Returns all avaliable user-owned entities related to given resource. 
        This method handles mute/block relationships and private/public visibilities.
        """
        # the foreign key field that points to resource
        # has to be named as the lower case name of that resource
        query_kwargs = {resource.__class__.__name__.lower(): resource}
        user_owned_entities = cls.objects.filter(
            **query_kwargs).order_by("-edited_time")

        # every user should only be abled to have one user owned entity for each resource
        # this is guaranteed by models
        id_list = []

        for entity in user_owned_entities:
            if entity.owner.mastodon_site == request_user.mastodon_site:
                id_list.append(entity.owner.mastodon_id)
            else:
                # TODO there could be many requests therefore make the pulling asynchronized
                id_list.append(get_cross_site_id(
                    entity.owner, request_user.mastodon_site, token))

        # Mastodon request
        relationships = get_relationships(
            request_user.mastodon_site, id_list, token)
        mute_block_blocked_index = []
        following_index = []
        for i, r in enumerate(relationships):
            # the order of relationships is corresponding to the id_list,
            # and the order of id_list is the same as user_owned_entiies
            if r['blocking'] or r['blocked_by'] or r['muting']:
                mute_block_blocked_index.append(i)
            if r['following']:
                following_index.append(i)
        available_entities = [
            e for i, e in enumerate(user_owned_entities)
                if ((e.is_private == True and i in following_index) or e.is_private == False or e.owner == request_user)
                    and not i in mute_block_blocked_index
        ]
        return available_entities

    @classmethod
    def get_available_user_data(cls, owner, is_following):
        """ 
        Returns all avaliable owner's entities. 

        :param owner: visited user
        :param is_following: if the current user is following the owner
        """
        user_owned_entities = cls.objects.filter(owner=owner)
        if not is_following:
            user_owned_entities = user_owned_entities.exclude(is_private=True)
        return user_owned_entities


# commonly used entity classes
###################################
class MarkStatusEnum(models.IntegerChoices):
    WISH = 1, _('Wish')
    DO = 2, _('Do')
    COLLECT = 3, _('Collect')


class Mark(UserOwnedEntity):
    status = models.SmallIntegerField(choices=MarkStatusEnum.choices)
    rating = models.PositiveSmallIntegerField(blank=True, null=True)
    text = models.CharField(max_length=500, blank=True, default='')

    def __str__(self):
        return f"({self.id}) {self.owner} {self.status}"

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(check=models.Q(
                rating__gte=0), name='mark_rating_lowerbound'),
            models.CheckConstraint(check=models.Q(
                rating__lte=10), name='mark_rating_upperbound'),
        ]


class Review(UserOwnedEntity):
    title = models.CharField(max_length=120)
    content = MarkdownxField()

    def __str__(self):
        return self.title

    class Meta:
        abstract = True


class Tag(models.Model):
    content = models.CharField(max_length=50)

    def __str__(self):
        return self.content

    class Meta:
        abstract = True
