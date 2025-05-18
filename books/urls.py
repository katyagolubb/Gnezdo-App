from django.urls import path
from books.views import BookSuggestionView, BookCreateView
from . import views

urlpatterns = [
    path('books/suggestions/', BookSuggestionView.as_view(), name='book-suggestions'),
    path('books/', BookCreateView.as_view(), name='book-create'),
    path('books/list/', views.UserBookListView.as_view(), name='user-book-list'),  # Read (List)
    path('books/<int:user_book_id>/', views.UserBookDetailView.as_view(), name='user-book-detail'),  # Read (Retrieve), Update, Delete
]