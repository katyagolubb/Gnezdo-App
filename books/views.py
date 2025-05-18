# books/views.py
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from django.conf import settings
from books.serializers import BookSuggestionSerializer, BookCreateSerializer, UserBookCreateSerializer
from books.models import Book, UserBook

class BookSuggestionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('query', '')
        if not query:
            return Response({"error": "Query parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        cache_key = f'suggestion_{query}'
        cached_response = cache.get(cache_key)
        if cached_response:
            return Response(cached_response)

        url = f"https://www.googleapis.com/books/v1/volumes?q={query}&key={settings.GOOGLE_API_KEY}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            suggestions = []
            for item in data.get('items', []):
                volume_info = item.get('volumeInfo', {})
                genres = volume_info.get('categories', ['Unknown'])
                normalized_genres = ', '.join(g.split('/')[-1].strip() for g in genres if '/' in g)
                if not normalized_genres and genres:
                    normalized_genres = genres[0].split('/')[-1].strip()
                suggestion = {
                    'id': item.get('id'),
                    'name': volume_info.get('title', ''),
                    'author': ', '.join(volume_info.get('authors', ['Unknown'])),
                    'overview': volume_info.get('description', ''),
                    'genres': normalized_genres,
                }
                suggestions.append(suggestion)
            cache.set(cache_key, suggestions, timeout=3600)
            return Response(suggestions)
        return Response({"error": "Failed to fetch suggestions"}, status=response.status_code)

class BookCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data

        # Проверяем, предоставлена ли книга через Google Books API или напрямую
        book_id = data.get('book_id')
        if book_id:
            # Если есть book_id, используем Google Books API
            url = f"https://www.googleapis.com/books/v1/volumes/{book_id}?key={settings.GOOGLE_API_KEY}"
            response = requests.get(url)
            if response.status_code != 200:
                return Response({"error": "Invalid book ID"}, status=response.status_code)

            book_data = response.json().get('volumeInfo', {})
            name = book_data.get('title', '')
            genres = book_data.get('categories', ['Unknown'])
            normalized_genres = ', '.join(g.split('/')[-1].strip() for g in genres if '/' in g)
            if not normalized_genres and genres:
                normalized_genres = genres[0].split('/')[-1].strip()

            book_data_to_save = {
                'name': name,
                'author': ', '.join(book_data.get('authors', ['Unknown'])),
                'overview': book_data.get('description', ''),
                'genres': normalized_genres,
            }
        else:
            # Если book_id нет, ожидаем данные книги от пользователя
            required_fields = ['name', 'author', 'overview', 'genres']
            for field in required_fields:
                if field not in data or not data[field]:
                    return Response({"error": f"{field} is required for custom book"}, status=status.HTTP_400_BAD_REQUEST)

            book_data_to_save = {
                'name': data['name'],
                'author': data['author'],
                'overview': data['overview'],
                'genres': data['genres'],
            }

        # Проверяем или создаём книгу по уникальному названию
        book, created = Book.objects.get_or_create(
            name=book_data_to_save['name'],
            defaults={
                'author': book_data_to_save['author'],
                'overview': book_data_to_save['overview'],
                'genres': book_data_to_save['genres'],
            }
        )

        # Сохранение в UserBook с обязательными полями
        user_book_data = {
            'user': user.id,
            'book_id': book.book_id,  # Ссылка на существующую или новую книгу
            'condition': data.get('condition', ''),
            'location': data.get('location', ''),
        }
        user_book_serializer = UserBookCreateSerializer(data=user_book_data)
        if user_book_serializer.is_valid():
            user_book_serializer.save()
            return Response({"message": "Book added successfully", "book_id": book.book_id}, status=status.HTTP_201_CREATED)
        return Response(user_book_serializer.errors, status=status.HTTP_400_BAD_REQUEST)