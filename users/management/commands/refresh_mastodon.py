from django.core.management.base import BaseCommand
from users.models import User
from django.utils import timezone
from django.conf import settings
from users.tasks import refresh_mastodon_relationships_task

class Command(BaseCommand):
    help = 'Refresh Mastodon data for all users if not updated in last 24h'

    refresh_mastodon_relationships_task()
