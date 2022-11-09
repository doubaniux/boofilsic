from django.contrib import admin
from .models import *
from simple_history.admin import SimpleHistoryAdmin

admin.site.register(Song, SimpleHistoryAdmin)
admin.site.register(SongMark)
admin.site.register(SongReview)
admin.site.register(SongTag)
admin.site.register(Album, SimpleHistoryAdmin)
admin.site.register(AlbumMark)
admin.site.register(AlbumReview)
admin.site.register(AlbumTag)
