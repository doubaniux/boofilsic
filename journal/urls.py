from django.urls import path, re_path
from .views import *


app_name = 'journal'
urlpatterns = [
    path('wish/<str:item_uuid>', wish, name='wish'),
    path('like/<str:piece_uuid>', like, name='like'),
    path('mark/<str:item_uuid>', mark, name='mark'),
    path('add_to_collection/<str:item_uuid>', add_to_collection, name='add_to_collection'),

    path('review/<str:piece_uuid>', review_retrieve, name='review_retrieve'),
    path('review/create', review_create, name='review_create'),
]
