from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ("id",)
    list_display = ("email", "username", "is_staff", "is_active", "date_joined")
    search_fields = ("email", "username")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("사용자 정보", {"fields": ("username", "first_name", "last_name")}),
        (
            "권한",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("접속 기록", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "username",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )
