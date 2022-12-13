from django.test import TestCase
from catalog.models import *
from journal.models import *
from .models import *
from users.models import User


class SocialTest(TestCase):
    def setUp(self):
        self.book1 = Edition.objects.create(title="Hyperion")
        self.book2 = Edition.objects.create(title="Andymion")
        self.alice = User.objects.create(mastodon_site="MySpace", username="Alice")
        self.alice.queue_manager.initialize()
        self.bob = User.objects.create(mastodon_site="KKCity", username="Bob")
        self.bob.queue_manager.initialize()

    def test_timeline(self):
        timeline = list(self.alice.activity_manager.get_viewable_activities())
        self.assertEqual(timeline, [])

        self.alice.queue_manager.update_for_item(self.book1, QueueType.WISHED)
        timeline = list(self.alice.activity_manager.get_viewable_activities())
        self.assertEqual(len(timeline), 1)
