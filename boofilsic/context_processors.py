from django.conf import settings


def site_info(request):
    return settings.SITE_INFO
