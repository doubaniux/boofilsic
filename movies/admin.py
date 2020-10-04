from django.contrib import admin
from .models import *

admin.site.register(Movie)
admin.site.register(MovieMark)
admin.site.register(MovieReview)
admin.site.register(MovieTag)
