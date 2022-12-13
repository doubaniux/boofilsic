from django.db import models
from polymorphic.models import PolymorphicModel
from users.models import User
from catalog.common.models import Item, ItemCategory
from catalog.common.mixins import SoftDeleteMixin
from .mixins import UserOwnedObjectMixin
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
import django.dispatch


class Piece(PolymorphicModel, UserOwnedObjectMixin):
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    visibility = models.PositiveSmallIntegerField(default=0)  # 0: Public / 1: Follower only / 2: Self only
    created_time = models.DateTimeField(auto_now_add=True)
    edited_time = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    metadata = models.JSONField(default=dict)
    attached_to = models.ForeignKey(User, null=True, default=None, on_delete=models.SET_NULL, related_name="attached_with")


class Content(SoftDeleteMixin, Piece):
    item: models.ForeignKey(Item, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.id}({self.item})"


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

list_add = django.dispatch.Signal()
list_remove = django.dispatch.Signal()


class List(Piece):
    class Meta:
        abstract = True

    _owner = models.ForeignKey(User, on_delete=models.PROTECT)  # duplicated owner field to make unique key possible for subclasses

    def save(self, *args, **kwargs):
        self._owner = self.owner
        super().save(*args, **kwargs)

    # MEMBER_CLASS = None  # subclass must override this
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
            p = {'_' + self.__class__.__name__.lower(): self}
            p.update(params)
            member = self.MEMBER_CLASS.objects.create(owner=self.owner, position=ml.last().position + 1 if ml.count() else 1, item=item, **p)
            list_add.send(sender=self.__class__, instance=self, item=item, member=member)
            return member

    def remove_item(self, item):
        member = self.members.all().filter(item=item).first()
        list_remove.send(sender=self.__class__, instance=self, item=item, member=member)
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


class ListMember(Piece):
    """
    ListMember - List class's member class
    It's an abstract class, subclass must add this:

    _list = models.ForeignKey('ListClass', related_name='members', on_delete=models.CASCADE)

    it starts with _ bc Django internally created OneToOne Field on Piece
    https://docs.djangoproject.com/en/3.2/topics/db/models/#specifying-the-parent-link-field
    """
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    position = models.PositiveIntegerField()

    class Meta:
        abstract = True

    def __str__(self):
        return f'{self.id}:{self.position} ({self.item})'


"""
Shelf
"""


class ShelfType(models.TextChoices):
    WISHED = ('wished', '未开始')
    STARTED = ('started', '进行中')
    DONE = ('done', '完成')
    # DISCARDED = ('discarded', '放弃')


ShelfTypeNames = [
    [ItemCategory.Book, ShelfType.WISHED, _('想读')],
    [ItemCategory.Book, ShelfType.STARTED, _('在读')],
    [ItemCategory.Book, ShelfType.DONE, _('读过')],
    [ItemCategory.Movie, ShelfType.WISHED, _('想看')],
    [ItemCategory.Movie, ShelfType.STARTED, _('在看')],
    [ItemCategory.Movie, ShelfType.DONE, _('看过')],
    [ItemCategory.TV, ShelfType.WISHED, _('想看')],
    [ItemCategory.TV, ShelfType.STARTED, _('在看')],
    [ItemCategory.TV, ShelfType.DONE, _('看过')],
    [ItemCategory.Music, ShelfType.WISHED, _('想听')],
    [ItemCategory.Music, ShelfType.STARTED, _('在听')],
    [ItemCategory.Music, ShelfType.DONE, _('听过')],
    [ItemCategory.Game, ShelfType.WISHED, _('想玩')],
    [ItemCategory.Game, ShelfType.STARTED, _('在玩')],
    [ItemCategory.Game, ShelfType.DONE, _('玩过')],
    [ItemCategory.Collection, ShelfType.WISHED, _('关注')],
    # TODO add more combinations
]


class ShelfMember(ListMember):
    _shelf = models.ForeignKey('Shelf', related_name='members', on_delete=models.CASCADE)


class Shelf(List):
    class Meta:
        unique_together = [['_owner', 'item_category', 'shelf_type']]

    MEMBER_CLASS = ShelfMember
    items = models.ManyToManyField(Item, through='ShelfMember', related_name="+")
    item_category = models.CharField(choices=ItemCategory.choices, max_length=100, null=False, blank=False)
    shelf_type = models.CharField(choices=ShelfType.choices, max_length=100, null=False, blank=False)

    def __str__(self):
        return f'{self.id} {self.title}'

    @cached_property
    def shelf_type_name(self):
        return next(iter([n[2] for n in iter(ShelfTypeNames) if n[0] == self.item_category and n[1] == self.shelf_type]), self.shelf_type)

    @cached_property
    def title(self):
        q = _("{item_category} {shelf_type_name} list").format(shelf_type_name=self.shelf_type_name, item_category=self.item_category)
        return _("{user}'s {shelf_name}").format(user=self.owner.mastodon_username, shelf_name=q)


class ShelfLogEntry(models.Model):
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    shelf = models.ForeignKey(Shelf, on_delete=models.PROTECT, related_name='entries', null=True)  # None means removed from any shelf
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    timestamp = models.DateTimeField(default=timezone.now)  # this may later be changed by user
    metadata = models.JSONField(default=dict)
    created_time = models.DateTimeField(auto_now_add=True)
    edited_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.owner}:{self.shelf}:{self.item}:{self.metadata}'


class ShelfManager:
    """
    ShelfManager

    all shelf operations should go thru this class so that ShelfLogEntry can be properly populated
    ShelfLogEntry can later be modified if user wish to change history
    """

    def __init__(self, user):
        self.owner = user

    def initialize(self):
        for ic in ItemCategory:
            for qt in ShelfType:
                Shelf.objects.create(owner=self.owner, item_category=ic, shelf_type=qt)

    def _shelf_member_for_item(self, item):
        return ShelfMember.objects.filter(item=item, _shelf__in=self.owner.shelf_set.all()).first()

    def _shelf_for_item_and_type(item, shelf_type):
        if not item or not shelf_type:
            return None
        return self.owner.shelf_set.all().filter(item_category=item.category, shelf_type=shelf_type)

    def move_item(self, item, shelf_type, visibility=0, metadata=None):
        # shelf_type=None means remove from current shelf
        # metadata=None means no change
        if not item:
            raise ValueError('empty item')
        lastqm = self._shelf_member_for_item(item)
        lastqmm = lastqm.metadata if lastqm else None
        lastq = lastqm._shelf if lastqm else None
        lastqt = lastq.shelf_type if lastq else None
        shelf = self.get_shelf(item.category, shelf_type) if shelf_type else None
        if lastq != shelf:
            if lastq:
                lastq.remove_item(item)
            if shelf:
                shelf.append_item(item, visibility=visibility, metadata=metadata or {})
        elif metadata is not None:
            lastqm.metadata = metadata
            lastqm.save()
        elif lastqm:
            metadata = lastqm.metadata
        if lastqt != shelf_type or (lastqt and metadata != lastqmm):
            ShelfLogEntry.objects.create(owner=self.owner, shelf=shelf, item=item, metadata=metadata or {})

    def get_log(self):
        return ShelfLogEntry.objects.filter(owner=self.owner).order_by('timestamp')

    def get_log_for_item(self, item):
        return ShelfLogEntry.objects.filter(owner=self.owner, item=item).order_by('timestamp')

    def get_shelf(self, item_category, shelf_type):
        return self.owner.shelf_set.all().filter(item_category=item_category, shelf_type=shelf_type).first()

    @staticmethod
    def get_manager_for_user(user):
        return ShelfManager(user)


User.shelf_manager = cached_property(ShelfManager.get_manager_for_user)
User.shelf_manager.__set_name__(User, 'shelf_manager')


"""
Collection
"""


class CollectionMember(ListMember):
    _collection = models.ForeignKey('Collection', related_name='members', on_delete=models.CASCADE)


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
    _tag = models.ForeignKey('Tag', related_name='members', on_delete=models.CASCADE)


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
