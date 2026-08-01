from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class User(AbstractUser):
    username = models.CharField("사용자 이름", max_length=30)
    email = models.EmailField("이메일", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        db_table = "user_account"
        ordering = ["id"]
        verbose_name = "사용자"
        verbose_name_plural = "사용자"

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email).lower()

    def __str__(self):
        return self.email
