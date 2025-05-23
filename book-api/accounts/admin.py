from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from accounts.models import User

class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['username', 'email', 'created_at', 'is_staff', 'is_active']
    list_filter = ['is_staff', 'is_active', 'created_at']
    search_fields = ['username', 'email']
    ordering = ['-created_at']
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )

admin.site.register(User, CustomUserAdmin)