from django.core.management.base import BaseCommand
from users.models import User
from datetime import timedelta
from django.utils import timezone


class Command(BaseCommand):
    help = 'Refresh Mastodon data for all users if not updated in last 24h'

    def handle(self, *args, **options):
        count = 0
        for user in User.objects.filter(mastodon_last_refresh__lt=timezone.now() - timedelta(hours=24)):
            if user.mastodon_token:
                print(f"Refreshing {user}")
                if user.refresh_mastodon_data():
                    print(f"Refreshed {user}")
                    count += 1
                else:
                    print(f"Refresh failed for {user}")
                user.save()
            else:
                print(f'Missing token for {user}')

        print(f'{count} users updated')
