from django.test import TestCase
from .models import *
from catalog.models import *
from users.models import User


class CollectionTest(TestCase):
    def setUp(self):
        self.book1 = Edition.objects.create(title="Hyperion")
        self.book2 = Edition.objects.create(title="Andymion")
        self.user = User.objects.create()
        pass

    def test_collection(self):
        collection = Collection.objects.create(title="test", owner=self.user)
        collection = Collection.objects.filter(title="test", owner=self.user).first()
        self.assertEqual(collection.catalog_item.title, "test")
        collection.append_item(self.book1)
        collection.append_item(self.book2)
        self.assertEqual(list(collection.ordered_items), [self.book1, self.book2])
        collection.move_up_item(self.book1)
        self.assertEqual(list(collection.ordered_items), [self.book1, self.book2])
        collection.move_up_item(self.book2)
        self.assertEqual(list(collection.ordered_items), [self.book2, self.book1])


class QueueTest(TestCase):
    def setUp(self):
        pass

    def test_queue(self):
        user = User.objects.create(mastodon_site="site", username="name")
        queue_manager = QueueManager(user=user)
        queue_manager.initialize()
        self.assertEqual(user.queue_set.all().count(), 30)
        book1 = Edition.objects.create(title="Hyperion")
        book2 = Edition.objects.create(title="Andymion")
        q1 = queue_manager.get_queue(ItemCategory.Book, QueueType.WISHED)
        q2 = queue_manager.get_queue(ItemCategory.Book, QueueType.STARTED)
        self.assertIsNotNone(q1)
        self.assertIsNotNone(q2)
        self.assertEqual(q1.members.all().count(), 0)
        self.assertEqual(q2.members.all().count(), 0)
        queue_manager.update_for_item(book1, QueueType.WISHED)
        queue_manager.update_for_item(book2, QueueType.WISHED)
        self.assertEqual(q1.members.all().count(), 2)
        queue_manager.update_for_item(book1, QueueType.STARTED)
        self.assertEqual(q1.members.all().count(), 1)
        self.assertEqual(q2.members.all().count(), 1)
        queue_manager.update_for_item(book1, QueueType.STARTED, metadata={'progress': 1})
        self.assertEqual(q1.members.all().count(), 1)
        self.assertEqual(q2.members.all().count(), 1)
        log = queue_manager.get_log_for_item(book1)
        self.assertEqual(log.count(), 3)
        queue_manager.update_for_item(book1, QueueType.STARTED, metadata={'progress': 1})
        log = queue_manager.get_log_for_item(book1)
        self.assertEqual(log.count(), 3)
        queue_manager.update_for_item(book1, QueueType.STARTED, metadata={'progress': 10})
        log = queue_manager.get_log_for_item(book1)
        self.assertEqual(log.count(), 4)
        queue_manager.update_for_item(book1, QueueType.STARTED)
        log = queue_manager.get_log_for_item(book1)
        self.assertEqual(log.count(), 4)
        self.assertEqual(log.order_by('queued_time').last().metadata, {'progress': 10})
        queue_manager.update_for_item(book1, QueueType.STARTED, metadata={'progress': 100})
        log = queue_manager.get_log_for_item(book1)
        self.assertEqual(log.count(), 5)


class TagTest(TestCase):
    def setUp(self):
        self.book1 = Edition.objects.create(title="Hyperion")
        self.book2 = Edition.objects.create(title="Andymion")
        self.movie1 = Edition.objects.create(title="Hyperion, The Movie")
        self.user1 = User.objects.create(mastodon_site="site", username="name")
        self.user2 = User.objects.create(mastodon_site="site2", username="name2")
        self.user3 = User.objects.create(mastodon_site="site2", username="name3")
        pass

    def test_tag(self):
        t1 = 'sci-fi'
        t2 = 'private'
        t3 = 'public'
        Tag.add_tag_by_user(self.book1, t3, self.user2)
        Tag.add_tag_by_user(self.book1, t1, self.user1)
        Tag.add_tag_by_user(self.book1, t1, self.user2)
        Tag.add_tag_by_user(self.book1, t2, self.user1, default_visibility=2)
        self.assertEqual(self.book1.tags, [t1, t3])
        Tag.add_tag_by_user(self.book1, t3, self.user1)
        Tag.add_tag_by_user(self.book1, t3, self.user3)
        self.assertEqual(self.book1.tags, [t3, t1])
        Tag.add_tag_by_user(self.book1, t3, self.user3)
        Tag.add_tag_by_user(self.book1, t3, self.user3)
        self.assertEqual(Tag.objects.count(), 6)
        Tag.add_tag_by_user(self.book2, t1, self.user2)
        self.assertEqual(self.user2.tags, [t1, t3])
        Tag.add_tag_by_user(self.book2, t3, self.user2)
        Tag.add_tag_by_user(self.movie1, t3, self.user2)
        self.assertEqual(self.user2.tags, [t3, t1])
