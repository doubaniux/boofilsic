import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from boofilsic.settings import REPORT_MEDIA_PATH_ROOT, DEFAULT_PASSWORD


def report_image_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = "%s.%s" % (uuid.uuid4(), ext)
    root = ''
    if REPORT_MEDIA_PATH_ROOT.endswith('/'):
        root = REPORT_MEDIA_PATH_ROOT
    else:
        root = REPORT_MEDIA_PATH_ROOT + '/'
    return root + timezone.now().strftime('%Y/%m/%d') + f'{filename}'


class User(AbstractUser):
    mastodon_id = models.IntegerField(blank=False)
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
        """ Automatically populate password field with DEFAULT_PASSWORD before saving."""
        self.set_password(DEFAULT_PASSWORD)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.username + '@' + self.mastodon_site


class Report(models.Model):
    submit_user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='sumbitted_reports', null=True)
    reported_user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='accused_reports', null=True)
    image = models.ImageField(upload_to=report_image_path, height_field=None, width_field=None, max_length=None, blank=True, default='')
    is_read = models.BooleanField(default=False)
    submitted_time = models.DateTimeField(auto_now_add=True)
    message = models.CharField(max_length=1000)



