from django.urls import path
from .views import *


app_name = 'sync'
urlpatterns = [
    path('douban/', sync_douban, name='douban'),
    path('progress/', query_progress, name='progress'),
    path('last/', query_last_task, name='last'),
]
