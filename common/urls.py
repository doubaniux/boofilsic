from django.urls import path
from .views import *

app_name = 'common'
urlpatterns = [
    path('', home),
    path('home/', home, name='home'),
    path('search/', search, name='search'),
    path('search.json/', search, name='search.json'),
    path('external_search/', external_search, name='external_search'),
]
