from django.urls import path, re_path
from .api import api
from .views import *
from .models import *


def _get_all_url_paths():
    paths = ['item']
    for cls in Item.__subclasses__():
        p = getattr(cls, 'url_path', None)
        if p:
            paths.append(p)
    res = "|".join(paths)
    return res


urlpatterns = [
    re_path(r'(?P<item_path>' + _get_all_url_paths() + ')/(?P<item_uid>[A-Za-z0-9]{21,22})/', retrieve, name='retrieve'),
    path("api/", api.urls),
]
