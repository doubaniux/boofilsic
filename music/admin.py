from django.contrib import admin
from .models import *

admin.site.register(Song)
admin.site.register(SongMark)
admin.site.register(SongReview)
admin.site.register(SongTag)
admin.site.register(Album)
admin.site.register(AlbumMark)
admin.site.register(AlbumReview)
admin.site.register(AlbumTag)
