from django.db import models
from polymorphic.models import PolymorphicModel
from users.models import User
from catalog.common.models import Item, ItemCategory
from catalog.collection.models import Collection as CatalogCollection
from decimal import *
from enum import Enum
from markdownx.models import MarkdownxField
from django.utils import timezone
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from functools import cached_property
from django.db.models import Count


class Piece(PolymorphicModel):
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    visibility = models.PositiveSmallIntegerField(default=0)  # 0: Public / 1: Follower only / 2: Self only
    metadata = models.JSONField(default=dict)
    created_time = models.DateTimeField(auto_now_add=True)
    edited_time = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    def clear(self):
        pass

    def delete(self, using=None, soft=True, *args, **kwargs):
        if soft:
            self.clear()
            self.is_deleted = True
            self.save(using=using)
        else:
            return super().delete(using=using, *args, **kwargs)

    def is_visible_to(self, viewer):
        if not viewer.is_authenticated:
            return self.visibility == 0
        owner = self.owner
        if owner == viewer:
            return True
        if not owner.is_active:
            return False
        if self.visibility == 2:
            return False
        if viewer.is_blocking(owner) or owner.is_blocking(viewer) or viewer.is_muting(owner):
            return False
        if self.visibility == 1:
            return viewer.is_following(owner)
        else:
            return True

    def is_editable_by(self, viewer):
        return True if viewer.is_staff or viewer.is_superuser or viewer == self.owner else False

    @classmethod
    def get_available(cls, entity, request_user, following_only=False):
        # e.g. SongMark.get_available(song, request.user)
        query_kwargs = {entity.__class__.__name__.lower(): entity}
        all_entities = cls.objects.filter(**query_kwargs).order_by("-created_time")  # get all marks for song
        visible_entities = list(filter(lambda _entity: _entity.is_visible_to(request_user) and (_entity.owner.mastodon_username in request_user.mastodon_following if following_only else True), all_entities))
        return visible_entities


class Content(Piece):
    target: models.ForeignKey(Item, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.id}({self.target})"


class Note(Content):
    pass


class Review(Content):
    warning = models.BooleanField(default=False)
    title = models.CharField(max_length=500, blank=False, null=True)
    body = MarkdownxField()
    pass


class Rating(Content):
    grade = models.IntegerField(default=0, validators=[MaxValueValidator(10), MinValueValidator(0)])


class Reply(Content):
    reply_to_content = models.ForeignKey(Content, on_delete=models.PROTECT, related_name='replies')
    title = models.CharField(max_length=500, null=True)
    body = MarkdownxField()
    pass


"""
List (abstract class)
"""


class List(Piece):
    class Meta:
        abstract = True

    _owner = models.ForeignKey(User, on_delete=models.PROTECT)  # duplicated owner field to make unique key possible for subclasses

    def save(self, *args, **kwargs):
        self._owner = self.owner
        super().save(*args, **kwargs)

    MEMBER_CLASS = None  # subclass must override this
    # subclass must add this:
    # items = models.ManyToManyField(Item, through='ListMember')

    @property
    def ordered_members(self):
        return self.members.all().order_by('position', 'item_id')

    @property
    def ordered_items(self):
        return self.items.all().order_by(self.MEMBER_CLASS.__name__.lower() + '__position')

    def has_item(self, item):
        return self.members.filter(item=item).count() > 0

    def append_item(self, item, **params):
        if item is None or self.has_item(item):
            return None
        else:
            ml = self.ordered_members
            p = {self.__class__.__name__.lower(): self}
            p.update(params)
            i = self.MEMBER_CLASS.objects.create(position=ml.last().position + 1 if ml.count() else 1, item=item, **p)
            return i

    def remove_item(self, item):
        member = self.members.all().filter(item=item).first()
        if member:
            member.delete()

    def move_up_item(self, item):
        members = self.ordered_members
        member = members.filter(item=item).first()
        if member:
            other = members.filter(position__lt=member.position).last()
            if other:
                p = other.position
                other.position = member.position
                member.position = p
                other.save()
                member.save()

    def move_down_item(self, item):
        members = self.ordered_members
        member = members.filter(item=item).first()
        if member:
            other = members.filter(position__gt=member.position).first()
            if other:
                p = other.position
                other.position = member.position
                member.position = p
                other.save()
                member.save()


class ListMember(models.Model):
    # subclass must add this:
    # list = models.ForeignKey('ListClass', related_name='members', on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    position = models.PositiveIntegerField()
    metadata = models.JSONField(default=dict)
    comment = models.ForeignKey(Review, on_delete=models.PROTECT, null=True)

    class Meta:
        abstract = True


"""
Queue
"""


class QueueType(models.TextChoices):
    WISHED = ('wished', '未开始')
    STARTED = ('started', '进行中')
    DONE = ('done', '完成')
    # DISCARDED = ('discarded', '放弃')


QueueTypeNames = [
    [ItemCategory.Book, QueueType.WISHED, _('想读')],
    [ItemCategory.Book, QueueType.STARTED, _('在读')],
    [ItemCategory.Book, QueueType.DONE, _('读过')],
    [ItemCategory.Movie, QueueType.WISHED, _('想看')],
    [ItemCategory.Movie, QueueType.STARTED, _('在看')],
    [ItemCategory.Movie, QueueType.DONE, _('看过')],
    [ItemCategory.TV, QueueType.WISHED, _('想看')],
    [ItemCategory.TV, QueueType.STARTED, _('在看')],
    [ItemCategory.TV, QueueType.DONE, _('看过')],
    [ItemCategory.Music, QueueType.WISHED, _('想听')],
    [ItemCategory.Music, QueueType.STARTED, _('在听')],
    [ItemCategory.Music, QueueType.DONE, _('听过')],
    [ItemCategory.Game, QueueType.WISHED, _('想玩')],
    [ItemCategory.Game, QueueType.STARTED, _('在玩')],
    [ItemCategory.Game, QueueType.DONE, _('玩过')],
    # TODO add more combinations
]


class QueueMember(ListMember):
    queue = models.ForeignKey('Queue', related_name='members', on_delete=models.CASCADE)


class Queue(List):
    class Meta:
        unique_together = [['_owner', 'item_category', 'queue_type']]

    MEMBER_CLASS = QueueMember
    items = models.ManyToManyField(Item, through='QueueMember', related_name="+")
    item_category = models.CharField(choices=ItemCategory.choices, max_length=100, null=False, blank=False)
    queue_type = models.CharField(choices=QueueType.choices, max_length=100, null=False, blank=False)

    def __str__(self):
        return f'{self.id} {self.title}'

    @cached_property
    def queue_type_name(self):
        return next(iter([n[2] for n in iter(QueueTypeNames) if n[0] == self.item_category and n[1] == self.queue_type]), self.queue_type)

    @cached_property
    def title(self):
        q = _("{item_category} {queue_type_name} list").format(queue_type_name=self.queue_type_name, item_category=self.item_category)
        return _("{user}'s {queue_name}").format(user=self.owner.mastodon_username, queue_name=q)


class QueueLogEntry(models.Model):
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    queue = models.ForeignKey(Queue, on_delete=models.PROTECT, related_name='entries', null=True)  # None means removed from any queue
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    metadata = models.JSONField(default=dict)
    created_time = models.DateTimeField(auto_now_add=True)
    edited_time = models.DateTimeField(auto_now=True)
    queued_time = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.owner}:{self.queue}:{self.item}:{self.metadata}'


class QueueManager:
    """
    QueueManager

    all queue operations should go thru this class so that QueueLogEntry can be properly populated
    QueueLogEntry can later be modified if user wish to change history
    """

    def __init__(self, user):
        self.owner = user

    def initialize(self):
        for ic in ItemCategory:
            if ic != ItemCategory.Collection:
                for qt in QueueType:
                    Queue.objects.create(owner=self.owner, item_category=ic, queue_type=qt)

    def _queue_member_for_item(self, item):
        return QueueMember.objects.filter(item=item, queue__in=self.owner.queue_set.all()).first()

    def _queue_for_item_and_type(item, queue_type):
        if not item or not queue_type:
            return None
        return self.owner.queue_set.all().filter(item_category=item.category, queue_type=queue_type)

    def update_for_item(self, item, queue_type, metadata=None):
        # None means no change for metadata, comment
        if not item:
            raise ValueError('empty item')
        lastqm = self._queue_member_for_item(item)
        lastqmm = lastqm.metadata if lastqm else None
        lastq = lastqm.queue if lastqm else None
        lastqt = lastq.queue_type if lastq else None
        queue = self.get_queue(item.category, queue_type) if queue_type else None
        if lastq != queue:
            if lastq:
                lastq.remove_item(item)
            if queue:
                queue.append_item(item, metadata=metadata or {})
        elif metadata is not None:
            lastqm.metadata = metadata
            lastqm.save()
        elif lastqm:
            metadata = lastqm.metadata
        if lastqt != queue_type or (lastqt and metadata != lastqmm):
            QueueLogEntry.objects.create(owner=self.owner, queue=queue, item=item, metadata=metadata or {})

    def get_log(self):
        return QueueLogEntry.objects.filter(owner=self.owner)

    def get_log_for_item(self, item):
        return QueueLogEntry.objects.filter(owner=self.owner, item=item)

    def get_queue(self, item_category, queue_type):
        return self.owner.queue_set.all().filter(item_category=item_category, queue_type=queue_type).first()


"""
Collection
"""


class CollectionMember(ListMember):
    collection = models.ForeignKey('Collection', related_name='members', on_delete=models.CASCADE)


class Collection(List):
    MEMBER_CLASS = CollectionMember
    catalog_item = models.OneToOneField(CatalogCollection, on_delete=models.PROTECT)
    title = models.CharField(_("title in primary language"), max_length=1000, default="")
    brief = models.TextField(_("简介"), blank=True, default="")
    items = models.ManyToManyField(Item, through='CollectionMember', related_name="collections")
    collaborative = models.PositiveSmallIntegerField(default=0)  # 0: Editable by owner only / 1: Editable by bi-direction followers

    @property
    def plain_description(self):
        html = markdown(self.description)
        return RE_HTML_TAG.sub(' ', html)

    def save(self, *args, **kwargs):
        if getattr(self, 'catalog_item', None) is None:
            self.catalog_item = CatalogCollection()
        if self.catalog_item.title != self.title or self.catalog_item.brief != self.brief:
            self.catalog_item.title = self.title
            self.catalog_item.brief = self.brief
            self.catalog_item.save()
        super().save(*args, **kwargs)


"""
Tag
"""


class TagMember(ListMember):
    tag = models.ForeignKey('Tag', related_name='members', on_delete=models.CASCADE)


TagValidators = [RegexValidator(regex=r'\s+', inverse_match=True)]


class Tag(List):
    MEMBER_CLASS = TagMember
    items = models.ManyToManyField(Item, through='TagMember')
    title = models.CharField(max_length=100, null=False, blank=False, validators=TagValidators)
    # TODO case convert and space removal on save
    # TODO check on save

    class Meta:
        unique_together = [['_owner', 'title']]

    @staticmethod
    def cleanup_title(title):
        return title.strip().lower()

    @staticmethod
    def public_tags_for_item(item):
        tags = item.tag_set.all().filter(visibility=0).values('title').annotate(frequency=Count('owner')).order_by('-frequency')
        return list(map(lambda t: t['title'], tags))

    @staticmethod
    def all_tags_for_user(user):
        tags = user.tag_set.all().values('title').annotate(frequency=Count('members')).order_by('-frequency')
        return list(map(lambda t: t['title'], tags))

    @staticmethod
    def add_tag_by_user(item, tag_title, user, default_visibility=0):
        title = Tag.cleanup_title(tag_title)
        tag = Tag.objects.filter(owner=user, title=title).first()
        if not tag:
            tag = Tag.objects.create(owner=user, title=title, visibility=default_visibility)
        tag.append_item(item)


Item.tags = property(Tag.public_tags_for_item)
User.tags = property(Tag.all_tags_for_user)
