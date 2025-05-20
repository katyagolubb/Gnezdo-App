from django.db import models
from accounts.models import User

class Book(models.Model):
    book_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    author = models.CharField(max_length=255)
    overview = models.TextField()
    genres = models.CharField(max_length=255)

    class Meta:
        db_table = 'books'

    def __str__(self):
        return self.name

class UserBook(models.Model):
    user_book_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book_id = models.ForeignKey(Book, on_delete=models.CASCADE)
    condition = models.CharField(max_length=255)
    location = models.CharField(max_length=255)

    class Meta:
        db_table = 'user_books'

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