# books/views.py
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from django.conf import settings
from books.serializers import (
    BookSuggestionSerializer, BookCreateSerializer, UserBookCreateSerializer,
    UserBookSerializer, PhotoSerializer, PhotoUploadSerializer, ExchangeRequestSerializer
)
from books.models import Book, UserBook, Photo, ExchangeRequest, Genre
from accounts.models import User
from django.contrib.auth import get_user_model
import cloudinary.uploader

# Существующие представления (оставляем без изменений)
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

        book_id = data.get('book_id')
        if book_id:
            url = f"https://www.googleapis.com/books/v1/volumes/{book_id}?key={settings.GOOGLE_API_KEY}"
            response = requests.get(url)
            if response.status_code != 200:
                return Response({"error": "Invalid book ID"}, status=response.status_code)

            book_data = response.json().get('volumeInfo', {})
            name = book_data.get('title', '')
            genres = book_data.get('categories', ['Unknown'])
            # Разбиваем жанры по слешам и сохраняем все уникальные части
            all_genres = set()
            for g in genres:
                parts = [part.strip() for part in g.split('/') if part.strip()]
                all_genres.update(parts)
            normalized_genres = ', '.join(all_genres) if all_genres else 'Unknown'
            logger.debug(f"Normalized genres from API: {normalized_genres}")

            book_data_to_save = {
                'name': name,
                'author': ', '.join(book_data.get('authors', ['Unknown'])),
                'overview': book_data.get('description', ''),
                'genres': normalized_genres,
            }
        else:
            required_fields = ['name', 'author', 'overview', 'genres']
            for field in required_fields:
                if field not in data or not data[field]:
                    return Response({"error": f"{field} is required for custom book"},
                                    status=status.HTTP_400_BAD_REQUEST)

            book_data_to_save = {
                'name': data['name'],
                'author': data['author'],
                'overview': data['overview'],
                'genres': data['genres'],
            }

        # Создаем книгу
        book, created = Book.objects.get_or_create(
            name=book_data_to_save['name'],
            defaults={
                'author': book_data_to_save['author'],
                'overview': book_data_to_save['overview'],
            }
        )

        # Обрабатываем жанры
        if 'genres' in book_data_to_save and book_data_to_save['genres']:
            genres_str = book_data_to_save['genres']
            genre_names = [g.strip() for g in genres_str.split(',') if g.strip()]
            logger.debug(f"Genre names to process: {genre_names}")
            if genre_names:
                genres_objects = []
                for name in genre_names:
                    genre, _ = Genre.objects.get_or_create(name=name)
                    genres_objects.append(genre)
                    logger.debug(f"Created/Found genre: {name}, ID: {genre.id}")
                book.genres.set(genres_objects)
                logger.debug(f"Genres set for book {book.book_id}: {list(book.genres.values_list('name', flat=True))}")
            else:
                logger.warning(f"No valid genres found in: {genres_str}")

        user_book_data = {
            'user': user.id,
            'book_id': book.book_id,
            'condition': data.get('condition', ''),
            'location': data.get('location', ''),
        }
        user_book_serializer = UserBookCreateSerializer(data=user_book_data)
        if user_book_serializer.is_valid():
            user_book_serializer.save()
            return Response({"message": "Book added successfully", "book_id": book.book_id, "genres": list(book.genres.values_list('name', flat=True))},
                            status=status.HTTP_201_CREATED)
        return Response(user_book_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

User = get_user_model()

class UserBookListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserBookSerializer

    def get_queryset(self):
        user_id = self.request.query_params.get('user_id')
        if user_id:
            try:
                target_user = User.objects.get(id=user_id)
                return UserBook.objects.filter(user=target_user).select_related('book_id')
            except User.DoesNotExist:
                return UserBook.objects.none()
        return UserBook.objects.filter(user=self.request.user).select_related('book_id')

class UserBookDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, user_book_id, user):
        try:
            user_book = UserBook.objects.get(user_book_id=user_book_id)
            if not user.is_superuser and user_book.user != user:
                return None
            return user_book
        except UserBook.DoesNotExist:
            return None

    def get(self, request, user_book_id):
        user_book = self.get_object(user_book_id, request.user)
        if not user_book:
            return Response({"error": "Book not found or access denied"}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserBookSerializer(user_book)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, user_book_id):
        user_book = self.get_object(user_book_id, request.user)
        if not user_book:
            return Response({"error": "Book not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        user_book_data = {
            'condition': data.get('condition', user_book.condition),
            'location': data.get('location', user_book.location),
            'user': user_book.user.id,
            'book_id': user_book.book_id.book_id,
        }
        serializer = UserBookCreateSerializer(user_book, data=user_book_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Book updated successfully"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, user_book_id):
        user_book = self.get_object(user_book_id, request.user)
        if not user_book:
            return Response({"error": "Book not found or access denied"}, status=status.HTTP_404_NOT_FOUND)
        user_book.delete()
        return Response({"message": "Book deleted successfully"}, status=status.HTTP_204_NO_CONTENT)

class BookSearchView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserBookSerializer

    def get_queryset(self):
        query = self.request.query_params.get('query', '')
        genres = self.request.query_params.get('genres', '')
        author = self.request.query_params.get('author', '')

        books = Book.objects.all()

        if query:
            books = books.filter(name__icontains=query)

        if genres:
            genre_list = [genre.strip() for genre in genres.split(',')]
            books = books.filter(genres__icontains=genre_list[0])
            for genre in genre_list[1:]:
                books = books.filter(genres__icontains=genre)

        if author:
            books = books.filter(author__icontains=author)

        if not books.exists():
            return UserBook.objects.none()

        return UserBook.objects.filter(
            book_id__in=books,
            status='available'  # Только доступные книги
        ).select_related('book_id').prefetch_related('photo_set')

class PhotoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PhotoUploadSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            file = serializer.validated_data['file']
            user_book = serializer.validated_data['user_book_id']

            try:
                upload_result = cloudinary.uploader.upload(
                    file,
                    folder=f"books/{user_book.user_book_id}",
                    resource_type="image"
                )
                file_path = upload_result['secure_url']

                photo = Photo.objects.create(
                    user_book_id=user_book,
                    file_path=file_path
                )

                photo_serializer = PhotoSerializer(photo)
                return Response(photo_serializer.data, status=status.HTTP_201_CREATED)

            except Exception as e:
                return Response({"error": f"Failed to upload to Cloudinary: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        user_book_id = request.query_params.get('user_book_id')
        if not user_book_id:
            return Response({"error": "user_book_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user_book = UserBook.objects.get(user_book_id=user_book_id)
        except UserBook.DoesNotExist:
            return Response({"error": "UserBook not found"}, status=status.HTTP_404_NOT_FOUND)

        photos = Photo.objects.filter(user_book_id=user_book)
        serializer = PhotoSerializer(photos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class PhotoDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, photo_id, user):
        try:
            photo = Photo.objects.get(photo_id=photo_id)
            if not user.is_superuser and photo.user_book_id.user != user:
                return None
            return photo
        except Photo.DoesNotExist:
            return None

    def delete(self, request, photo_id):
        photo = self.get_object(photo_id, request.user)
        if not photo:
            return Response({"error": "Photo not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

        try:
            public_id = photo.file_path.split('/')[-1].split('.')[0]
            cloudinary.uploader.destroy(
                f"books/{photo.user_book_id.user_book_id}/{public_id}",
                resource_type="image"
            )

            photo.delete()
            return Response({"message": "Photo deleted successfully"}, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({"error": f"Failed to delete from Cloudinary: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, photo_id):
        photo = self.get_object(photo_id, request.user)
        if not photo:
            return Response({"error": "Photo not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

        serializer = PhotoUploadSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            file = serializer.validated_data['file']

            try:
                public_id = photo.file_path.split('/')[-1].split('.')[0]
                cloudinary.uploader.destroy(
                    f"books/{photo.user_book_id.user_book_id}/{public_id}",
                    resource_type="image"
                )

                upload_result = cloudinary.uploader.upload(
                    file,
                    folder=f"books/{photo.user_book_id.user_book_id}",
                    resource_type="image"
                )
                new_file_path = upload_result['secure_url']

                photo.file_path = new_file_path
                photo.save()

                photo_serializer = PhotoSerializer(photo)
                return Response(photo_serializer.data, status=status.HTTP_200_OK)

            except Exception as e:
                return Response({"error": f"Failed to update photo in Cloudinary: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Новые представления для обмена
class ExchangeRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        POST /api/exchange-requests/ - Создание запроса на обмен
        """
        user_book_id = request.data.get('user_book_id')
        if not user_book_id:
            return Response({"error": "user_book_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user_book = UserBook.objects.get(user_book_id=user_book_id)
        except UserBook.DoesNotExist:
            return Response({"error": "Book not found"}, status=status.HTTP_404_NOT_FOUND)

        # Проверка статуса книги
        if user_book.status != 'available':
            return Response({"error": "Book is not available for exchange"}, status=status.HTTP_400_BAD_REQUEST)

        # Нельзя запросить свою же книгу
        if user_book.user == request.user:
            return Response({"error": "You cannot request your own book"}, status=status.HTTP_400_BAD_REQUEST)

        # Создание запроса
        exchange_request = ExchangeRequest.objects.create(
            book=user_book,
            requester=request.user,
            owner=user_book.user,
            status='pending'
        )

        # Обновление статуса книги
        user_book.status = 'requested'
        user_book.save()

        serializer = ExchangeRequestSerializer(exchange_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ExchangeRequestDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, exchange_request_id, user):
        try:
            exchange_request = ExchangeRequest.objects.get(exchange_request_id=exchange_request_id)
            if not user.is_superuser and exchange_request.owner != user:
                return None
            return exchange_request
        except ExchangeRequest.DoesNotExist:
            return None

    def patch(self, request, exchange_request_id):
        """
        PATCH /api/exchange-requests/<id>/ - Принятие или отклонение запроса
        """
        exchange_request = self.get_object(exchange_request_id, request.user)
        if not exchange_request:
            return Response({"error": "Request not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')  # 'accept' или 'reject'
        if not action:
            return Response({"error": "Action is required ('accept' or 'reject')"}, status=status.HTTP_400_BAD_REQUEST)

        if exchange_request.status != 'pending':
            return Response({"error": "Request is not in pending status"}, status=status.HTTP_400_BAD_REQUEST)

        if action == 'accept':
            exchange_request.status = 'accepted'
            exchange_request.book.status = 'exchanged'
            exchange_request.book.save()
        elif action == 'reject':
            exchange_request.status = 'rejected'
            exchange_request.book.status = 'available'
            exchange_request.book.save()
        else:
            return Response({"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)

        exchange_request.save()
        serializer = ExchangeRequestSerializer(exchange_request)
        return Response(serializer.data, status=status.HTTP_200_OK)

class UserExchangeListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ExchangeRequestSerializer

    def get_queryset(self):
        # Книги, которые пользователь запросил (взял)
        requested = ExchangeRequest.objects.filter(requester=self.request.user)
        # Книги, которые пользователь отдал (его книги, которые запросили другие)
        owned = ExchangeRequest.objects.filter(owner=self.request.user)
        return requested.union(owned)