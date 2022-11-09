from django.urls import path, re_path
from .views import *


app_name = 'timeline'
urlpatterns = [
    path('', timeline, name='timeline'),
    path('data', data, name='data'),
]
