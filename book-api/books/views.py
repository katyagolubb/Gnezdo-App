# books/views.py
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from django.conf import settings
from books.serializers import BookSuggestionSerializer, BookCreateSerializer, UserBookCreateSerializer, UserBookSerializer, PhotoSerializer, PhotoUploadSerializer
from books.models import Book, UserBook, Photo
from accounts.models import User
from django.contrib.auth import get_user_model
import cloudinary.uploader

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
                return None  # Ограничение доступа для обычных пользователей
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

        # Начинаем с базового набора книг
        books = Book.objects.all()

        # Фильтрация по названию, если указано
        if query:
            books = books.filter(name__icontains=query)

        # Фильтрация по жанрам, если указано
        if genres:
            genre_list = [genre.strip() for genre in genres.split(',')]
            books = books.filter(genres__icontains=genre_list[0])
            for genre in genre_list[1:]:
                books = books.filter(genres__icontains=genre)

        # Фильтрация по автору, если указано
        if author:
            books = books.filter(author__icontains=author)

        # Если после фильтрации книг нет, возвращаем пустой queryset
        if not books.exists():
            return UserBook.objects.none()

        # Возвращаем записи UserBook, связанные с отфильтрованными книгами
        return UserBook.objects.filter(book_id__in=books).select_related('book_id').prefetch_related('photo_set')

class PhotoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        POST /api/photos/ - Загрузка фото
        """
        serializer = PhotoUploadSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            # Загрузка файла в Cloudinary
            file = serializer.validated_data['file']
            user_book = serializer.validated_data['user_book_id']

            try:
                # Загрузка файла в Cloudinary
                upload_result = cloudinary.uploader.upload(
                    file,
                    folder=f"books/{user_book.user_book_id}",  # Храним в папке books/<user_book_id>
                    resource_type="image"
                )
                file_path = upload_result['secure_url']  # Публичный URL файла

                # Сохранение записи в базе
                photo = Photo.objects.create(
                    user_book_id=user_book,
                    file_path=file_path
                )

                # Сериализация ответа
                photo_serializer = PhotoSerializer(photo)
                return Response(photo_serializer.data, status=status.HTTP_201_CREATED)

            except Exception as e:
                return Response({"error": f"Failed to upload to Cloudinary: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        """
        GET /api/photos/?user_book_id=<id> - Получение списка фотографий
        """
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
            # Проверка прав доступа
            if not user.is_superuser and photo.user_book_id.user != user:
                return None
            return photo
        except Photo.DoesNotExist:
            return None

    def delete(self, request, photo_id):
        """
        DELETE /api/photos/<id>/ - Удаление фото
        """
        photo = self.get_object(photo_id, request.user)
        if not photo:
            return Response({"error": "Photo not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

        try:
            # Извлечение public_id из URL Cloudinary
            public_id = photo.file_path.split('/')[-1].split('.')[0]
            cloudinary.uploader.destroy(
                f"books/{photo.user_book_id.user_book_id}/{public_id}",
                resource_type="image"
            )

            # Удаление записи из базы
            photo.delete()
            return Response({"message": "Photo deleted successfully"}, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({"error": f"Failed to delete from Cloudinary: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, photo_id):
        """
        PATCH /api/photos/<id>/ - Обновление фото
        """
        photo = self.get_object(photo_id, request.user)
        if not photo:
            return Response({"error": "Photo not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

        serializer = PhotoUploadSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            file = serializer.validated_data['file']

            try:
                # Удаление старого файла из Cloudinary
                public_id = photo.file_path.split('/')[-1].split('.')[0]
                cloudinary.uploader.destroy(
                    f"books/{photo.user_book_id.user_book_id}/{public_id}",
                    resource_type="image"
                )

                # Загрузка нового файла в Cloudinary
                upload_result = cloudinary.uploader.upload(
                    file,
                    folder=f"books/{photo.user_book_id.user_book_id}",
                    resource_type="image"
                )
                new_file_path = upload_result['secure_url']

                # Обновление записи в базе
                photo.file_path = new_file_path
                photo.save()

                # Сериализация ответа
                photo_serializer = PhotoSerializer(photo)
                return Response(photo_serializer.data, status=status.HTTP_200_OK)

            except Exception as e:
                return Response({"error": f"Failed to update photo in Cloudinary: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)