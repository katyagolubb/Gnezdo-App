from django.urls import path
from .views import (
    BookSuggestionView, BookCreateView, UserBookListView,
    UserBookDetailView, BookSearchView, PhotoView, PhotoDetailView
)

urlpatterns = [
    path('books/suggestions/', BookSuggestionView.as_view(), name='book-suggestions'),
    path('books/', BookCreateView.as_view(), name='book-create'),
    path('books/list/', UserBookListView.as_view(), name='user-book-list'),  # Read (List)
    path('books/<int:user_book_id>/', UserBookDetailView.as_view(), name='user-book-detail'),  # Read (Retrieve), Update, Delete
    path('books/search/', BookSearchView.as_view(), name='book-search'),
    path('books/photos/', PhotoView.as_view(), name='photo-list-create'),
    path('books/photos/<int:photo_id>/', PhotoDetailView.as_view(), name='photo-detail'),
]