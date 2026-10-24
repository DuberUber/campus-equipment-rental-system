from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ['username', 'last_name', 'first_name', 'email', 'student_number', 'course', 'year', 'is_staff']
    list_filter = DjangoUserAdmin.list_filter + ('year',)
    search_fields = ['username', 'last_name', 'first_name', 'email', 'student_number']
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Student details', {'fields': ['student_number', 'course', 'year']}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ('Contact', {'fields': ['email', 'first_name', 'last_name']}),
    )
