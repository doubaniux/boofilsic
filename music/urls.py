from django.urls import path, re_path
from .views import *


app_name = 'music'
urlpatterns = [
    path('song/create/', create_song, name='create_song'),
    path('song/<int:id>/', retrieve_song, name='retrieve_song'),
    path('song/update/<int:id>/', update_song, name='update_song'),
    path('song/delete/<int:id>/', delete_song, name='delete_song'),
    path('song/mark/', create_update_song_mark, name='create_update_song_mark'),
    path('song/<int:song_id>/mark/list/',
         retrieve_song_mark_list, name='retrieve_song_mark_list'),
    path('song/mark/delete/<int:id>/', delete_song_mark, name='delete_song_mark'),
    path('song/<int:song_id>/review/create/', create_song_review, name='create_song_review'),
    path('song/review/update/<int:id>/', update_song_review, name='update_song_review'),
    path('song/review/delete/<int:id>/', delete_song_review, name='delete_song_review'),
    path('song/review/<int:id>/', retrieve_song_review, name='retrieve_song_review'),
    re_path('song/(?P<song_id>[0-9]+)/mark/list/(?:(?P<following_only>\\d+))?', retrieve_song_mark_list, name='retrieve_song_mark_list'),
#     path('song/scrape/', scrape_song, name='scrape_song'),
    path('song/click_to_scrape/', click_to_scrape_song, name='click_to_scrape_song'),
    
    path('album/create/', create_album, name='create_album'),
    path('album/<int:id>/', retrieve_album, name='retrieve_album'),
    path('album/update/<int:id>/', update_album, name='update_album'),
    path('album/delete/<int:id>/', delete_album, name='delete_album'),
    path('album/mark/', create_update_album_mark, name='create_update_album_mark'),
    re_path('album/(?P<album_id>[0-9]+)/mark/list/(?:(?P<following_only>\\d+))?', retrieve_album_mark_list, name='retrieve_album_mark_list'),
    path('album/mark/delete/<int:id>/', delete_album_mark, name='delete_album_mark'),
    path('album/<int:album_id>/review/create/', create_album_review, name='create_album_review'),
    path('album/review/update/<int:id>/', update_album_review, name='update_album_review'),
    path('album/review/delete/<int:id>/', delete_album_review, name='delete_album_review'),
    path('album/review/<int:id>/', retrieve_album_review, name='retrieve_album_review'),
    path('album/<int:album_id>/review/list/',
         retrieve_album_review_list, name='retrieve_album_review_list'),
    path('album/scrape/', scrape_album, name='scrape_album'),
    path('album/click_to_scrape/', click_to_scrape_album, name='click_to_scrape_album'),
]
