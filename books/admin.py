# books/admin.py
from django.contrib import admin
from books.models import Book, UserBook, Photo

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['book_id', 'name', 'author', 'genres']

@admin.register(UserBook)
class UserBookAdmin(admin.ModelAdmin):
    list_display = ['user_book_id', 'user_id', 'book_id', 'condition', 'location']

@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ['photo_id', 'user_book_id']