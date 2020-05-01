from django.urls import path
from .views import *


app_name = 'books'
urlpatterns = [
    path('create/', create, name='create'),
    path('<int:id>/', retrieve, name='retrieve'),
]
