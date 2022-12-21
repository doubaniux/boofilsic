from django.urls import path, re_path
from .views import *


app_name = 'journal'
urlpatterns = [
    path('wish/<str:item_uuid>', wish, name='wish'),
    path('like/<str:piece_uuid>', like, name='like'),
]
