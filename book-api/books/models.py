from django.db import models
from accounts.models import User

class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Book(models.Model):
    book_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    author = models.CharField(max_length=255)
    overview = models.TextField()
    genres = models.ManyToManyField(Genre, blank=True)

    class Meta:
        db_table = 'books'
        indexes = [
            models.Index(fields=['name'], name='idx_book_name'),
            models.Index(fields=['author'], name='idx_book_author'),
        ]

    def __str__(self):
        return self.name

class UserBook(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('requested', 'Requested'),
        ('exchanged', 'Exchanged'),
    )

    user_book_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book_id = models.ForeignKey(Book, on_delete=models.CASCADE)
    condition = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')

    class Meta:
        db_table = 'user_books'
        indexes = [
            models.Index(fields=['user', 'status'], name='idx_userbook_user_status'),
            models.Index(fields=['book_id'], name='idx_userbook_book_id'),
        ]

    def __str__(self):
        return f"{self.book_id.name} (User: {self.user.username})"
class Photo(models.Model):
    photo_id = models.AutoField(primary_key=True)
    user_book_id = models.ForeignKey(UserBook, on_delete=models.CASCADE)
    file_path = models.CharField(max_length=255)

    class Meta:
        db_table = 'photo'

    def __str__(self):
        return f"Photo for {self.user_book_id}"

class ExchangeRequest(models.Model):
    REQUEST_STATUS_CHOICES = (
        ('pending', 'Pending'),  # Запрос ожидает подтверждения
        ('accepted', 'Accepted'),  # Запрос принят
        ('rejected', 'Rejected'),  # Запрос отклонён
        ('completed', 'Completed'),  # Обмен завершён
    )

    exchange_request_id = models.AutoField(primary_key=True)
    book = models.ForeignKey(UserBook, on_delete=models.CASCADE, related_name='exchange_requests')
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requested_books')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_books')
    status = models.CharField(max_length=20, choices=REQUEST_STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'exchange_requests'

    def __str__(self):
        return f"Request for {self.book} by {self.requester.username}"