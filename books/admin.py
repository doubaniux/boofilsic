from django.contrib import admin
from .models import *
from simple_history.admin import SimpleHistoryAdmin

admin.site.register(Book, SimpleHistoryAdmin)
admin.site.register(BookMark)
admin.site.register(BookReview)
admin.site.register(BookTag)

