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


class ShelfTest(TestCase):
    def setUp(self):
        pass

    def test_shelf(self):
        user = User.objects.create(mastodon_site="site", username="name")
        shelf_manager = ShelfManager(user=user)
        shelf_manager.initialize()
        self.assertEqual(user.shelf_set.all().count(), 33)
        book1 = Edition.objects.create(title="Hyperion")
        book2 = Edition.objects.create(title="Andymion")
        q1 = shelf_manager.get_shelf(ItemCategory.Book, ShelfType.WISHED)
        q2 = shelf_manager.get_shelf(ItemCategory.Book, ShelfType.STARTED)
        self.assertIsNotNone(q1)
        self.assertIsNotNone(q2)
        self.assertEqual(q1.members.all().count(), 0)
        self.assertEqual(q2.members.all().count(), 0)
        shelf_manager.move_item(book1, ShelfType.WISHED)
        shelf_manager.move_item(book2, ShelfType.WISHED)
        self.assertEqual(q1.members.all().count(), 2)
        shelf_manager.move_item(book1, ShelfType.STARTED)
        self.assertEqual(q1.members.all().count(), 1)
        self.assertEqual(q2.members.all().count(), 1)
        shelf_manager.move_item(book1, ShelfType.STARTED, metadata={'progress': 1})
        self.assertEqual(q1.members.all().count(), 1)
        self.assertEqual(q2.members.all().count(), 1)
        log = shelf_manager.get_log_for_item(book1)
        self.assertEqual(log.count(), 3)
        shelf_manager.move_item(book1, ShelfType.STARTED, metadata={'progress': 1})
        log = shelf_manager.get_log_for_item(book1)
        self.assertEqual(log.count(), 3)
        shelf_manager.move_item(book1, ShelfType.STARTED, metadata={'progress': 10})
        log = shelf_manager.get_log_for_item(book1)
        self.assertEqual(log.count(), 4)
        shelf_manager.move_item(book1, ShelfType.STARTED)
        log = shelf_manager.get_log_for_item(book1)
        self.assertEqual(log.count(), 4)
        self.assertEqual(log.last().metadata, {'progress': 10})
        shelf_manager.move_item(book1, ShelfType.STARTED, metadata={'progress': 100})
        log = shelf_manager.get_log_for_item(book1)
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
        TagManager.add_tag_by_user(self.book1, t3, self.user2)
        TagManager.add_tag_by_user(self.book1, t1, self.user1)
        TagManager.add_tag_by_user(self.book1, t1, self.user2)
        TagManager.add_tag_by_user(self.book1, t2, self.user1, default_visibility=2)
        self.assertEqual(self.book1.tags, [t1, t3])
        TagManager.add_tag_by_user(self.book1, t3, self.user1)
        TagManager.add_tag_by_user(self.book1, t3, self.user3)
        self.assertEqual(self.book1.tags, [t3, t1])
        TagManager.add_tag_by_user(self.book1, t3, self.user3)
        TagManager.add_tag_by_user(self.book1, t3, self.user3)
        self.assertEqual(Tag.objects.count(), 6)
        TagManager.add_tag_by_user(self.book2, t1, self.user2)
        self.assertEqual(self.user2.tags, [t1, t3])
        TagManager.add_tag_by_user(self.book2, t3, self.user2)
        TagManager.add_tag_by_user(self.movie1, t3, self.user2)
        self.assertEqual(self.user2.tags, [t3, t1])


class MarkTest(TestCase):
    def setUp(self):
        self.book1 = Edition.objects.create(title="Hyperion")
        self.user1 = User.objects.create(mastodon_site="site", username="name")
        self.user1.shelf_manager.initialize()
        pass

    def test_mark(self):
        mark = Mark(self.user1, self.book1)
        self.assertEqual(mark.shelf_type, None)
        self.assertEqual(mark.shelf_label, None)
        self.assertEqual(mark.text, None)
        self.assertEqual(mark.rating, None)
        self.assertEqual(mark.visibility, None)
        self.assertEqual(mark.review, None)
        self.assertEqual(mark.tags, [])
        mark.update(ShelfType.WISHED, 'a gentle comment', 9, 1)

        mark = Mark(self.user1, self.book1)
        self.assertEqual(mark.shelf_type, ShelfType.WISHED)
        self.assertEqual(mark.shelf_label, '想读')
        self.assertEqual(mark.text, 'a gentle comment')
        self.assertEqual(mark.rating, 9)
        self.assertEqual(mark.visibility, 1)
        self.assertEqual(mark.review, None)
        self.assertEqual(mark.tags, [])

        review = Review.review_item_by_user(self.book1, self.user1, 'Critic', 'Review')
        mark = Mark(self.user1, self.book1)
        self.assertEqual(mark.review, review)

        self.user1.tag_manager.add_item_tags(self.book1, [' Sci-Fi ', ' fic '])
        mark = Mark(self.user1, self.book1)
        self.assertEqual(mark.tags, ['sci-fi', 'fic'])
