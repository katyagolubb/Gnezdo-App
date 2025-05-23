# books/admin.py
from django.contrib import admin
from books.models import Book, UserBook, Photo, Genre


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['book_id', 'name', 'author', 'display_genres']
    filter_horizontal = ['genres']  # Добавляет удобный интерфейс для выбора жанров

    def display_genres(self, obj):
        return ", ".join([genre.name for genre in obj.genres.all()])

    display_genres.short_description = 'Genres'


@admin.register(UserBook)
class UserBookAdmin(admin.ModelAdmin):
    list_display = ['user_book_id', 'user', 'book', 'condition', 'location']

    # Если нужно отображать имя пользователя вместо объекта
    def user(self, obj):
        return obj.user.username

    user.short_description = 'User'

    # Если нужно отображать название книги вместо объекта
    def book(self, obj):
        return obj.book_id.name

    book.short_description = 'Book'


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ['photo_id', 'user_book']

    # Если нужно отображать информацию о связи вместо объекта
    def user_book(self, obj):
        return f"{obj.user_book_id.book_id.name} (User: {obj.user_book_id.user.username})"

    user_book.short_description = 'User Book'


# Дополнительно можно зарегистрировать модель Genre
@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']