from django.contrib import admin
from .models import *
from simple_history.admin import SimpleHistoryAdmin

admin.site.register(Movie, SimpleHistoryAdmin)
admin.site.register(MovieMark)
admin.site.register(MovieReview)
admin.site.register(MovieTag)
