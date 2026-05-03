from django.contrib import admin

from .models import Institute, UserProfile, Attendance

admin.site.register(Institute)
admin.site.register(UserProfile)
admin.site.register(Attendance)
