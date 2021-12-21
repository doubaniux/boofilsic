from django.urls import path, re_path
from .views import *


app_name = 'collection'
urlpatterns = [
    path('create/', create, name='create'),
    path('<int:id>/', retrieve, name='retrieve'),
    path('update/<int:id>/', update, name='update'),
    path('delete/<int:id>/', delete, name='delete'),
    path('follow/<int:id>/', follow, name='follow'),
    path('unfollow/<int:id>/', follow, name='unfollow'),
    path('with/<str:type>/<int:id>/', list_with, name='list_with'),
    # TODO: tag
]
