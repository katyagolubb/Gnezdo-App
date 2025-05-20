from django.contrib.auth.models import AbstractUser
from django.db import models
from cloudinary.models import CloudinaryField

class User(AbstractUser):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    first_name = models.CharField(max_length=30, blank=True)  # Имя
    last_name = models.CharField(max_length=30, blank=True)  # Фамилия
    phone = models.CharField(max_length=15, blank=True, null=True)  # Телефон
    photo = CloudinaryField(
        'image',
        folder='users/',  # Указываем папку для фото пользователей
        blank=True,
        null=True
    )

    def __str__(self):
        return self.username