import uuid
import django.contrib.postgres.fields as postgres
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.translation import gettext_lazy as _
from common.utils import GenerateDateUUIDMediaFilePath
from django.conf import settings
from mastodon.api import *


def report_image_path(instance, filename):
    return GenerateDateUUIDMediaFilePath(instance, filename, settings.REPORT_MEDIA_PATH_ROOT)


class User(AbstractUser):
    if settings.MASTODON_ALLOW_ANY_SITE:
        username = models.CharField(
            _('username'),
            max_length=150,
            unique=False,
            help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        )
    mastodon_id = models.CharField(max_length=100, blank=False)
    # mastodon domain name, eg donotban.com
    mastodon_site = models.CharField(max_length=100, blank=False)
    mastodon_token = models.CharField(max_length=100, default='')
    mastodon_refresh_token = models.CharField(max_length=100, default='')
    mastodon_locked = models.BooleanField(default=False)
    mastodon_followers = models.JSONField(default=list)
    mastodon_following = models.JSONField(default=list)
    mastodon_mutes = models.JSONField(default=list)
    mastodon_blocks = models.JSONField(default=list)
    mastodon_domain_blocks = models.JSONField(default=list)
    mastodon_account = models.JSONField(default=dict)
    mastodon_last_refresh = models.DateTimeField(default=timezone.now)
    # store the latest read announcement id, 
    # every time user read the announcement update this field
    read_announcement_index = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['username', 'mastodon_site'], name="unique_user_identity")
        ]

    # def save(self, *args, **kwargs):
    #     """ Automatically populate password field with settings.DEFAULT_PASSWORD before saving."""
    #     self.set_password(settings.DEFAULT_PASSWORD)
    #     return super().save(*args, **kwargs)

    @property
    def mastodon_username(self):
        return self.username + '@' + self.mastodon_site

    def __str__(self):
        return self.mastodon_username

    def refresh_mastodon_data(self):
        """ Try refresh account data from mastodon server, return true if refreshed successfully, note it will not save to db """
        self.mastodon_last_refresh = timezone.now()
        code, mastodon_account = verify_account(self.mastodon_site, self.mastodon_token)
        updated = False
        if mastodon_account:
            self.mastodon_account = mastodon_account
            self.mastodon_locked = mastodon_account['locked']
            # self.mastodon_token = token
            # user.mastodon_id  = mastodon_account['id']
            self.mastodon_followers = get_related_acct_list(self.mastodon_site, self.mastodon_token, f'/api/v1/accounts/{self.mastodon_id}/followers')
            self.mastodon_following = get_related_acct_list(self.mastodon_site, self.mastodon_token, f'/api/v1/accounts/{self.mastodon_id}/following')
            self.mastodon_mutes = get_related_acct_list(self.mastodon_site, self.mastodon_token, '/api/v1/mutes')
            self.mastodon_blocks = get_related_acct_list(self.mastodon_site, self.mastodon_token, '/api/v1/blocks')
            self.mastodon_domain_blocks = get_related_acct_list(self.mastodon_site, self.mastodon_token, '/api/v1/domain_blocks')
            updated = True
        elif code == 401:
            print(f'401 {self}')
            self.mastodon_token = ''
        return updated

    def is_blocking(self, target):
        return target.mastodon_username in self.mastodon_blocks or target.mastodon_site in self.mastodon_domain_blocks

    def is_blocked_by(self, target):
        return target.is_blocking(self)

    def is_muting(self, target):
        return target.mastodon_username in self.mastodon_mutes

    def is_following(self, target):
        return self.mastodon_username in target.mastodon_followers if target.mastodon_locked else self.mastodon_username in target.mastodon_followers or target.mastodon_username in self.mastodon_following

    def is_followed_by(self, target):
        return target.is_following(self)


class Preference(models.Model):
    user = models.OneToOneField(User, models.CASCADE, primary_key=True)
    home_layout = postgres.ArrayField(
        postgres.HStoreField(),
        blank=True,
        default=list,
    )
    export_status = models.JSONField(blank=True, null=True, encoder=DjangoJSONEncoder, default=dict)
    mastodon_publish_public = models.BooleanField(null=False, default=False)

    def get_serialized_home_layout(self):
        return str(self.home_layout).replace("\'", "\"")

    def __str__(self):
        return str(self.user)


class Report(models.Model):
    submit_user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='sumbitted_reports', null=True)
    reported_user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='accused_reports', null=True)
    image = models.ImageField(upload_to=report_image_path, height_field=None, width_field=None, max_length=None, blank=True, default='')
    is_read = models.BooleanField(default=False)
    submitted_time = models.DateTimeField(auto_now_add=True)
    message = models.CharField(max_length=1000)
