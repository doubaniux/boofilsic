from django.urls import path
from .views import *

app_name = 'users'
urlpatterns = [
    path('login/', login, name='login'),
    path('register/', register, name='register'),
    path('connect/', connect, name='connect'),
    path('logout/', logout, name='logout'),
    path('delete/', delete, name='delete'),
    path('layout/', set_layout, name='set_layout'),
    path('OAuth2_login/', OAuth2_login, name='OAuth2_login'),
    path('<int:id>/', home, name='home'),
    path('<int:id>/followers/', followers, name='followers'),
    path('<int:id>/following/', following, name='following'),
    path('<int:id>/book/<str:status>/', book_list, name='book_list'),
    path('<int:id>/movie/<str:status>/', movie_list, name='movie_list'),
    path('<int:id>/music/<str:status>/', music_list, name='music_list'),
    path('<int:id>/game/<str:status>/', game_list, name='game_list'),
    path('<str:id>/', home, name='home'),
    path('<str:id>/followers/', followers, name='followers'),
    path('<str:id>/following/', following, name='following'),
    path('<str:id>/book/<str:status>/', book_list, name='book_list'),
    path('<str:id>/movie/<str:status>/', movie_list, name='movie_list'),
    path('report/', report, name='report'),
    path('manage_report/', manage_report, name='manage_report'),
]
