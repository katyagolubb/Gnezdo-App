from django.urls import path
from .views import (
    BookSuggestionView, BookCreateView, UserBookListView,
    UserBookDetailView, BookSearchView, PhotoView, PhotoDetailView,
    ExchangeRequestView, ExchangeRequestDetailView, UserExchangeListView, UserBookOwnersView, AllUserBooksView
)

urlpatterns = [
    path('books/suggestions/', BookSuggestionView.as_view(), name='book-suggestions'),
    path('books/', BookCreateView.as_view(), name='book-create'),
    path('books/list/', UserBookListView.as_view(), name='user-book-list'),
    path('books/<int:user_book_id>/', UserBookDetailView.as_view(), name='user-book-detail'),
    path('books/search/', BookSearchView.as_view(), name='book-search'),
    path('books/photos/', PhotoView.as_view(), name='photo-list-create'),
    path('books/photos/<int:photo_id>/', PhotoDetailView.as_view(), name='photo-detail'),
    path('exchange-requests/', ExchangeRequestView.as_view(), name='exchange-request-create'),
    path('exchange-requests/<int:exchange_request_id>/', ExchangeRequestDetailView.as_view(), name='exchange-request-detail'),
    path('exchange-requests/list/', UserExchangeListView.as_view(), name='user-exchange-list'),
    path('books/owners/', UserBookOwnersView.as_view(), name='user-book-owners'),
    path('books/all/', AllUserBooksView.as_view(), name='all-user-books'),
]