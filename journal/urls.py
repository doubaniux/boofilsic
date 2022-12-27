from django.urls import path, re_path
from .views import *
from catalog.models import *


app_name = 'journal'


def _get_all_categories():
    res = "|".join(CATEGORY_LIST.keys())
    return res


def _get_all_shelf_types():
    return "|".join(ShelfType.values)


urlpatterns = [
    path('wish/<str:item_uuid>', wish, name='wish'),
    path('like/<str:piece_uuid>', like, name='like'),
    path('mark/<str:item_uuid>', mark, name='mark'),
    path('add_to_collection/<str:item_uuid>', add_to_collection, name='add_to_collection'),

    path('review/<str:review_uuid>', review_retrieve, name='review_retrieve'),
    path('review/create/<str:item_uuid>/', review_edit, name='review_create'),
    path('review/edit/<str:item_uuid>/<str:review_uuid>', review_edit, name='review_edit'),
    path('review/delete/<str:review_uuid>', review_delete, name='review_delete'),

    re_path(r'^user/(?P<user_name>[A-Za-z0-0_\-.@]+)/(?P<shelf_type>' + _get_all_shelf_types() + ')/(?P<item_category>' + _get_all_categories() + ')/$', user_mark_list, name='user_mark_list'),
    re_path(r'^user/(?P<user_name>[A-Za-z0-0_\-.@]+)/reviews/(?P<item_category>' + _get_all_categories() + ')/$', user_review_list, name='user_review_list'),
    re_path(r'^user/(?P<user_name>[A-Za-z0-0_\-.@]+)/tags/(?P<tag_title>[^/]+)/$', user_tag_member_list, name='user_tag_member_list'),
    re_path(r'^user/(?P<user_name>[A-Za-z0-0_\-.@]+)/collections/$', user_collection_list, name='user_collection_list'),
    re_path(r'^user/(?P<user_name>[A-Za-z0-0_\-.@]+)/like/collections/$', user_liked_collection_list, name='user_liked_collection_list'),
    re_path(r'^user/(?P<user_name>[A-Za-z0-0_\-.@]+)/tags/$', user_tag_list, name='user_tag_list'),

]
