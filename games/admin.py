from django.contrib import admin
from .models import *
from simple_history.admin import SimpleHistoryAdmin

admin.site.register(Game, SimpleHistoryAdmin)
admin.site.register(GameMark)
admin.site.register(GameReview)
admin.site.register(GameTag)
