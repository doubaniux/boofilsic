import django.contrib.postgres.fields as postgres
from decimal import *
from django.utils.translation import ugettext_lazy as _
from django.db import models, IntegrityError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from markdownx.models import MarkdownxField
from users.models import User
from common.mastodon.api import get_relationships


# abstract base classes
###################################
class Resource(models.Model):

    rating_total_score = models.PositiveIntegerField(null=True, blank=True)
    rating_number = models.PositiveIntegerField(null=True, blank=True)
    rating = models.DecimalField(null=True, blank=True, max_digits=3, decimal_places=1)
    created_time = models.DateTimeField(auto_now_add=True)
    edited_time = models.DateTimeField(auto_now_add=True)
    last_editor = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='%(class)s_last_editor', null=True, blank=False)
    brief = models.TextField(blank=True, default="")
    other_info = postgres.JSONField(blank=True, null=True, encoder=DjangoJSONEncoder, default=dict)

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(check=models.Q(rating__gte=0), name='%(class)s_rating_lowerbound'),
            models.CheckConstraint(check=models.Q(rating__lte=10), name='%(class)s_rating_upperbound'),
        ]        

    def save(self, *args, **kwargs):
        """ update rating before save to db """
        if self.rating_number and self.rating_total_score:
            self.rating = Decimal(str(round(self.rating_total_score  / self.rating_number, 1)))
        elif self.rating_number is None and self.rating_total_score is None:
            self.rating = None
        else:
            raise IntegrityError()
        super().save(*args, **kwargs)

    def calculate_rating(self, old_rating, new_rating):
        if (not (self.rating and self.rating_total_score and self.rating_number)\
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


class UserOwnedEntity(models.Model):
    is_private = models.BooleanField()
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_%(class)ss')
    created_time = models.DateTimeField(auto_now_add=True)
    edited_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    @classmethod
    def get_available(cls, resource, user, token):
        """ 
        Returns all avaliable user-owned entities related to given resource. 
        This method handls mute/block relationships and private/public visibilities.
        """
        # the foreign key field that points to resource 
        # has to be named as the lower case name of that resource
        query_kwargs = {resource.__class__.__name__.lower(): resource}
        user_owned_entities = cls.objects.filter(**query_kwargs).order_by("-edited_time")
        # every user should only be abled to have one user owned entity for each resource
        # this is guaranteed by models
        id_list = [e.owner.mastodon_id for e in user_owned_entities]
        # Mastodon request
        # relationships = get_relationships(id_list, token)
        # mute_block_blocked = []
        # following = []
        # for r in relationships:
        #     # check json data type
        #     if r['blocking'] or r['blocked_by'] or r['muting']:
        #         mute_block_blocked.append(r['id'])
        #     if r['following']:
        #         following.append(r['id'])
        # user_owned_entities = user_owned_entities.exclude(owner__mastodon_id__in=mute_block_blocked)
        # following.append(str(user.mastodon_id))
        # user_owned_entities = user_owned_entities.exclude(Q(is_private=True) & ~Q(owner__mastodon_id__in=following))
        return user_owned_entities


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

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(check=models.Q(rating__gte=0), name='mark_rating_lowerbound'),
            models.CheckConstraint(check=models.Q(rating__lte=10), name='mark_rating_upperbound'),
        ]


class Review(UserOwnedEntity):
    title = models.CharField(max_length=120)
    content = MarkdownxField()

    def __str__(self):
        return self.title

    class Meta:
        abstract = True
