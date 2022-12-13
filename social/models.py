"""
Models for Social app

DataSignalManager captures create/update/(soft/hard)delete from Journal app, and generate Activity objects,
ActivityManager generates chronological view for user and, in future, ActivityStreams

"""

from django.db import models
from users.models import User
from catalog.common.models import Item
from journal.models import *
import logging
from functools import cached_property
from django.db.models.signals import post_save, post_delete, pre_delete
from django.db.models import Q


_logger = logging.getLogger(__name__)


class ActionType(models.TextChoices):
    Create = 'create'
    Delete = 'delete'
    Update = 'update'
    Add = 'add'
    Remove = 'remove'
    Like = 'like'
    Undo_Like = 'undo_like'
    Announce = 'announce'
    Undo_Announce = 'undo_announce'
    Follow = 'follow'
    Undo_Follow = 'undo_follow'
    Flag = 'flag'
    Move = 'move'
    Accept = 'accept'
    Reject = 'reject'
    Block = 'block'
    Undo_Block = 'undo_block'


class ActivityManager:
    def __init__(self, user):
        self.owner = user

    def get_viewable_activities(self, before_time=None):
        q = Q(owner_id__in=self.owner.following, visibility__lt=2) | Q(owner=self.owner)
        q = q & Q(is_viewable=True)
        if before_time:
            q = q & Q(created_time__lt=before_time)
        return Activity.objects.filter(q)

    @staticmethod
    def get_manager_for_user(user):
        return ActivityManager(user)


User.activity_manager = cached_property(ActivityManager.get_manager_for_user)
User.activity_manager.__set_name__(User, 'activity_manager')


class Activity(models.Model, UserOwnedObjectMixin):
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    visibility = models.PositiveSmallIntegerField(default=0)  # 0: Public / 1: Follower only / 2: Self only
    action_type = models.CharField(blank=False, choices=ActionType.choices, max_length=50)
    action_object = models.ForeignKey(Piece, on_delete=models.SET_NULL, null=True)
    is_viewable = models.BooleanField(default=True)  # if viewable in local time line, otherwise it's event only for s2s
    # action_uid = TODO

    @property
    def target(self):
        return get_attself.action_object

    @property
    def action_class(self):
        return self.action_object.__class__.__name__

    def __str__(self):
        return f'{self.id}:{self.action_type}:{self.action_object}:{self.is_viewable}'


class DefaultSignalProcessor():
    def __init__(self, action_object):
        self.action_object = action_object

    def activity_viewable(self, action_type):
        return action_type == ActionType.Create and bool(getattr(self.action_object, 'attached_to', None) is None)

    def created(self):
        activity = Activity.objects.create(owner=self.action_object.owner, visibility=self.action_object.visibility, action_object=self.action_object, action_type=ActionType.Create, is_viewable=self.activity_viewable(ActionType.Create))
        return activity

    def updated(self):
        create_activity = Activity.objects.filter(owner=self.action_object.owner, action_object=self.action_object, action_type=ActionType.Create).first()
        action_type = ActionType.Update if create_activity else ActionType.Create
        is_viewable = self.activity_viewable(action_type)
        return Activity.objects.create(owner=self.action_object.owner, visibility=self.action_object.visibility, action_object=self.action_object, action_type=action_type, is_viewable=is_viewable)

    def deleted(self):
        create_activity = Activity.objects.filter(owner=self.action_object.owner, action_object=self.action_object, action_type=ActionType.Create).first()
        if create_activity:
            create_activity.is_viewable = False
            create_activity.save()
        else:
            _logger.warning(f'unable to find create activity for {self.action_object}')
        # FIXME action_object=self.action_object causing issues in test when hard delete, the bare minimum is to save id of the actual object that ActivityPub requires
        return Activity.objects.create(owner=self.action_object.owner, visibility=self.action_object.visibility, action_object=None, action_type=ActionType.Delete, is_viewable=self.activity_viewable(ActionType.Delete))


class UnhandledSignalProcessor(DefaultSignalProcessor):
    def created(self):
        _logger.warning(f'unhandled created signal for {self.action_object}')

    def updated(self):
        _logger.warning(f'unhandled updated signal for {self.action_object}')

    def deleted(self):
        _logger.warning(f'unhandled deleted signal for {self.action_object}')


class DataSignalManager:
    processors = {}

    @staticmethod
    def save_handler(sender, instance, created, **kwargs):
        processor_class = DataSignalManager.processors.get(instance.__class__)
        if not processor_class:
            processor_class = GenericSignalProcessor
        processor = processor_class(instance)
        if created:
            processor.created()
        elif getattr(instance, 'is_deleted', False):
            processor.deleted()
        else:
            processor.updated()

    @staticmethod
    def delete_handler(sender, instance, **kwargs):
        processor_class = DataSignalManager.processors.get(instance.__class__)
        if not processor_class:
            processor_class = GenericSignalProcessor
        processor = processor_class(instance)
        processor.deleted()

    @staticmethod
    def add_handler_for_model(model):
        post_save.connect(DataSignalManager.save_handler, sender=model)
        pre_delete.connect(DataSignalManager.delete_handler, sender=model)

    @staticmethod
    def register(processor):
        DataSignalManager.add_handler_for_model(processor.model)
        DataSignalManager.processors[processor.model] = processor
        return processor


@DataSignalManager.register
class MarkProcessor(DefaultSignalProcessor):
    model = ShelfMember


# @DataSignalManager.register
# class ReplyProcessor(DefaultSignalProcessor):
#     model = Reply

#     def activity_viewable(self):
#         return False


# @DataSignalManager.register
# class RatingProcessor(DefaultSignalProcessor):
#     model = Rating


@DataSignalManager.register
class ReviewProcessor(DefaultSignalProcessor):
    model = Review


@DataSignalManager.register
class CollectionProcessor(DefaultSignalProcessor):
    model = Collection
