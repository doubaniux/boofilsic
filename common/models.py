import django.contrib.postgres.fields as postgres
from decimal import *
from django.utils.translation import ugettext_lazy as _
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder
from markdownx.models import MarkdownxField
from users.models import User


# abstract base classes
###################################
class Resource(models.Model):

    rating_total_score = models.PositiveIntegerField(null=True, blank=True)
    rating_number = models.PositiveIntegerField(null=True, blank=True)
    rating = models.DecimalField(null=True, blank=True, max_digits=2, decimal_places=1)
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
            self.rating = Decimal(str(round(self.rating_total_score  / self.rating_number ), 1))
        super().save(*args, **kwargs)


class UserOwnedEntity(models.Model):
    is_private = models.BooleanField()
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='user_%(class)ss', null=True)
    created_time = models.DateTimeField(auto_now_add=True)
    edited_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


# commonly used entity classes
###################################
class MarkStatusEnum(models.IntegerChoices):
    DO = 1, _('Do')
    WISH = 2, _('Wish')
    COLLECT = 3, _('Collect')


class Mark(UserOwnedEntity):
    status = models.SmallIntegerField(choices=MarkStatusEnum.choices)
    rating = models.PositiveSmallIntegerField(blank=True, null=True)
    text = models.CharField(max_length=150, blank=True, default='')

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