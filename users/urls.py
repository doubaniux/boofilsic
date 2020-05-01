from django.urls import path
from .views import *

app_name = 'users'
urlpatterns = [
    path('login/', login, name='login'),
    path('register/', register, name='register'),
    path('logout/', logout, name='logout'),
    path('delete/', delete, name='delete'),
    path('OAuth2_login/', OAuth2_login, name='OAuth2_login'),
]
