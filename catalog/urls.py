from django.urls import path, re_path
from .api import api
from .views import *


urlpatterns = [
    path("", api.urls),
    re_path('book/(?P<uid>[A-Za-z0-9]{21,22})/', retrieve, name='retrieve'),
]
