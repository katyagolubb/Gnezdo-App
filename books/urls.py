from django.urls import path
from books.views import BookSuggestionView, BookCreateView

urlpatterns = [
    path('books/suggestions/', BookSuggestionView.as_view(), name='book-suggestions'),
    path('books/', BookCreateView.as_view(), name='book-create'),
]