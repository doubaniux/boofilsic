from django.contrib import admin
from .models import *

admin.site.register(Book)
admin.site.register(BookMark)
admin.site.register(BookReview)
admin.site.register(BookTag)

