import uuid
import django.contrib.postgres.fields as postgres
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.translation import ugettext_lazy as _
from common.utils import GenerateDateUUIDMediaFilePath
from django.conf import settings


def report_image_path(instance, filename):
    return GenerateDateUUIDMediaFilePath(instance, filename, settings.REPORT_MEDIA_PATH_ROOT)


class User(AbstractUser):
    mastodon_id = models.CharField(max_length=100, blank=False)
    # mastodon domain name, eg donotban.com
    mastodon_site = models.CharField(max_length=100, blank=False)
    # store the latest read announcement id, 
    # every time user read the announcement update this field
    read_announcement_index = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['username', 'mastodon_site'], name="unique_user_identity")
        ]

    def save(self, *args, **kwargs):
        """ Automatically populate password field with settings.DEFAULT_PASSWORD before saving."""
        self.set_password(settings.DEFAULT_PASSWORD)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.username + '@' + self.mastodon_site


class Preference(models.Model):
    user = models.OneToOneField(User, models.CASCADE, primary_key=True)
    home_layout = postgres.ArrayField(
        postgres.HStoreField(),
        blank=True,
        default=list,
    )

    def get_serialized_home_layout(self):
        return str(self.home_layout).replace("\'","\"")

    def __str__(self):
        return str(self.user)


class Report(models.Model):
    submit_user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='sumbitted_reports', null=True)
    reported_user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='accused_reports', null=True)
    image = models.ImageField(upload_to=report_image_path, height_field=None, width_field=None, max_length=None, blank=True, default='')
    is_read = models.BooleanField(default=False)
    submitted_time = models.DateTimeField(auto_now_add=True)
    message = models.CharField(max_length=1000)
