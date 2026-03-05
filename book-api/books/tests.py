# books/tests.py
"""
Модульные тесты для book-api.
Покрывают функциональные требования F1–F6:
F1: Добавление книги (вручную / из выбора)
F2: Список своих книг
F3: Список книг другого пользователя
F4: Детальная информация о книге
F5: Обновление книги (состояние, описание, жанр)
F6: Удаление книги
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework import status
import responses

from books.models import Book, UserBook, Genre, ExchangeRequest
from books.serializers import BookCreateSerializer, UserBookCreateSerializer

User = get_user_model()


# --- Вспомогательные данные ---

def make_user(username='user1', **kwargs):
    return User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='testpass123',
        **kwargs
    )


def make_book(name='Test Book', author='Test Author', overview='Overview', genres_str='Fiction'):
    book = Book.objects.create(name=name, author=author, overview=overview)
    for g in [x.strip() for x in genres_str.split(',') if x.strip()]:
        genre, _ = Genre.objects.get_or_create(name=g)
        book.genres.add(genre)
    return book


def make_user_book(user, book=None, condition='OK', location='55.7558,37.6173'):
    book = book or make_book()
    return UserBook.objects.create(
        user=user,
        book_id=book,
        condition=condition,
        location=location,
    )


# --- Модели (F1–F6 косвенно) ---

class BookModelTest(TestCase):
    """Тесты модели Book."""

    def test_book_creation(self):
        book = make_book(name='Harry Potter', author='J.K. Rowling', overview='Magic', genres_str='Fantasy')
        self.assertEqual(book.name, 'Harry Potter')
        self.assertEqual(book.author, 'J.K. Rowling')
        self.assertEqual(book.overview, 'Magic')
        self.assertEqual(list(book.genres.values_list('name', flat=True)), ['Fantasy'])

    def test_book_str(self):
        book = make_book(name='1984')
        self.assertIn('1984', str(book))


class UserBookModelTest(TestCase):
    """Тесты модели UserBook."""

    def test_userbook_creation(self):
        user = make_user('owner')
        ub = make_user_book(user, condition='Excellent', location='55.75,37.61')
        self.assertEqual(ub.user, user)
        self.assertEqual(ub.condition, 'Excellent')
        self.assertEqual(ub.status, 'available')

    def test_userbook_status_choices(self):
        self.assertIn(('available', 'Available'), UserBook.STATUS_CHOICES)


class GenreModelTest(TestCase):
    """Тесты модели Genre."""

    def test_genre_creation(self):
        g = Genre.objects.create(name='Sci-Fi')
        self.assertEqual(str(g), 'Sci-Fi')


# --- Сериализаторы (F1, F5) ---

class BookCreateSerializerTest(TestCase):
    """F1: Валидация создания книги вручную."""

    def test_valid_manual_book(self):
        """F1: Сериализатор валидирует данные для ручного создания книги."""
        data = {
            'name': 'Valid Book Name',
            'author': 'Valid Author',
            'overview': 'Short description',
            'genres': 'Fiction, Adventure',
        }
        s = BookCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['name'], 'Valid Book Name')
        self.assertEqual(s.validated_data['author'], 'Valid Author')
        self.assertIn('genres', s.validated_data)

    def test_missing_name(self):
        data = {'author': 'Author', 'overview': 'x', 'genres': 'Fiction'}
        s = BookCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('name', s.errors)

    def test_missing_author(self):
        data = {'name': 'Book', 'overview': 'x', 'genres': 'Fiction'}
        s = BookCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('author', s.errors)

    def test_genres_normalization(self):
        data = {'name': 'B', 'author': 'A', 'overview': 'o', 'genres': 'Fantasy / Adventure'}
        s = BookCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)


class UserBookCreateSerializerTest(TestCase):
    """F1, F5: Валидация UserBook."""

    def setUp(self):
        self.user = make_user('u1')
        self.book = make_book()

    def test_valid_userbook(self):
        data = {
            'user': self.user.id,
            'book_id': self.book.book_id,
            'condition': 'Good',
            'location': '55.7558,37.6173',
        }
        s = UserBookCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        ub = s.save()
        self.assertEqual(ub.condition, 'Good')

    def test_invalid_condition_empty(self):
        data = {
            'user': self.user.id,
            'book_id': self.book.book_id,
            'condition': '',
            'location': '55.75,37.61',
        }
        s = UserBookCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('condition', s.errors)

    def test_invalid_location_format(self):
        data = {
            'user': self.user.id,
            'book_id': self.book.book_id,
            'condition': 'OK',
            'location': 'invalid',
        }
        s = UserBookCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('location', s.errors)


# --- API Views (F1–F6) ---

class BookCreateAPITest(TestCase):
    """F1: Добавление книги вручную через API."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user('creator')
        self.client.force_authenticate(user=self.user)

    def test_create_book_manually_success(self):
        """F1: Успешное добавление книги вручную."""
        data = {
            'name': 'My Custom Book',
            'author': 'John Doe',
            'overview': 'A great story',
            'genres': 'Fiction, Adventure',
            'condition': 'Good',
            'location': '55.7558,37.6173',
        }
        resp = self.client.post('/api/books/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', resp.json())
        self.assertIn('book_id', resp.json())

    def test_create_book_missing_name(self):
        """F1: Ошибка при отсутствии названия."""
        data = {
            'author': 'Author',
            'overview': 'x',
            'genres': 'Fiction',
            'condition': 'OK',
            'location': '55.75,37.61',
        }
        resp = self.client.post('/api/books/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', resp.json())

    def test_create_book_missing_author(self):
        """F1: Ошибка при отсутствии автора."""
        data = {
            'name': 'Book',
            'overview': 'x',
            'genres': 'Fiction',
            'condition': 'OK',
            'location': '55.75,37.61',
        }
        resp = self.client.post('/api/books/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_book_missing_genres(self):
        """F1: Ошибка при отсутствии жанра."""
        data = {
            'name': 'Book',
            'author': 'Author',
            'overview': 'x',
            'condition': 'OK',
            'location': '55.75,37.61',
        }
        resp = self.client.post('/api/books/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_book_unauthenticated(self):
        """F1: Неавторизованный запрос отклоняется."""
        self.client.force_authenticate(user=None)
        resp = self.client.post('/api/books/', {
            'name': 'B', 'author': 'A', 'overview': 'o', 'genres': 'F',
            'condition': 'OK', 'location': '55.75,37.61',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class UserBookListAPITest(TestCase):
    """F2, F3: Список книг пользователя."""

    def setUp(self):
        self.client = APIClient()
        self.user1 = make_user('user1')
        self.user2 = make_user('user2')
        self.client.force_authenticate(user=self.user1)

    def test_list_own_books(self):
        """F2: Список своих книг."""
        make_user_book(self.user1, make_book('B1'), condition='OK')
        make_user_book(self.user1, make_book('B2'), condition='Good')
        resp = self.client.get('/api/books/list/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn('results', data)
        self.assertEqual(len(data['results']), 2)

    def test_list_own_books_empty(self):
        """F2: Пустой список своих книг."""
        resp = self.client.get('/api/books/list/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.json())
        self.assertEqual(len(resp.json()['results']), 0)

    def test_list_another_user_books(self):
        """F3: Список книг другого пользователя."""
        make_user_book(self.user2, make_book('Other Book'), condition='OK')
        resp = self.client.get('/api/books/list/', {'user_id': self.user2.id})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.json().get('results', [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['book']['name'], 'Other Book')

    def test_list_another_user_nonexistent(self):
        """F3: Несуществующий user_id — пустой список."""
        resp = self.client.get('/api/books/list/', {'user_id': 99999})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.json().get('results', [])), 0)

    def test_list_books_unauthenticated(self):
        """F2/F3: Неавторизованный запрос."""
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/books/list/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class UserBookDetailAPITest(TestCase):
    """F4: Детальная информация о книге."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user('owner')
        self.client.force_authenticate(user=self.user)
        self.ub = make_user_book(
            self.user,
            make_book('Detail Book', 'Detail Author', 'Overview here', 'Fiction'),
            condition='Excellent',
            location='55.75,37.61',
        )

    def test_get_book_detail_success(self):
        """F4: Успешное получение деталей книги."""
        resp = self.client.get(f'/api/books/{self.ub.user_book_id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data['book']['name'], 'Detail Book')
        self.assertEqual(data['book']['author'], 'Detail Author')
        self.assertEqual(data['book']['overview'], 'Overview here')
        self.assertEqual(data['condition'], 'Excellent')
        self.assertIn('genres', data['book'])

    def test_get_book_detail_not_found(self):
        """F4: Книга не найдена."""
        resp = self.client.get('/api/books/99999/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_book_detail_access_denied_other_user(self):
        """F4: Доступ к чужой книге запрещён."""
        other = make_user('other')
        self.client.force_authenticate(user=other)
        resp = self.client.get(f'/api/books/{self.ub.user_book_id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class UserBookUpdateAPITest(TestCase):
    """F5: Обновление книги."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user('owner')
        self.client.force_authenticate(user=self.user)
        self.ub = make_user_book(self.user, condition='OK', location='55.75,37.61')

    def test_update_book_success(self):
        """F5: Успешное обновление состояния и локации."""
        resp = self.client.put(
            f'/api/books/{self.ub.user_book_id}/',
            {'condition': 'Excellent', 'location': '40.71,-74.00'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.ub.refresh_from_db()
        self.assertEqual(self.ub.condition, 'Excellent')
        self.assertEqual(self.ub.location, '40.71,-74.00')

    def test_update_book_partial(self):
        """F5: Частичное обновление (только condition)."""
        resp = self.client.put(
            f'/api/books/{self.ub.user_book_id}/',
            {'condition': 'Good'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.ub.refresh_from_db()
        self.assertEqual(self.ub.condition, 'Good')

    def test_update_book_not_found(self):
        """F5: Обновление несуществующей книги."""
        resp = self.client.put(
            '/api/books/99999/',
            {'condition': 'OK', 'location': '55.75,37.61'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_book_access_denied(self):
        """F5: Обновление чужой книги запрещено."""
        other = make_user('other')
        self.client.force_authenticate(user=other)
        resp = self.client.put(
            f'/api/books/{self.ub.user_book_id}/',
            {'condition': 'Bad'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class UserBookDeleteAPITest(TestCase):
    """F6: Удаление книги."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user('owner')
        self.client.force_authenticate(user=self.user)
        self.ub = make_user_book(self.user)

    def test_delete_book_success(self):
        """F6: Успешное удаление книги."""
        ub_id = self.ub.user_book_id
        resp = self.client.delete(f'/api/books/{ub_id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(UserBook.objects.filter(user_book_id=ub_id).exists())

    def test_delete_book_not_found(self):
        """F6: Удаление несуществующей книги."""
        resp = self.client.delete('/api/books/99999/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_book_access_denied(self):
        """F6: Удаление чужой книги запрещено."""
        other = make_user('other')
        self.client.force_authenticate(user=other)
        resp = self.client.delete(f'/api/books/{self.ub.user_book_id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(UserBook.objects.filter(user_book_id=self.ub.user_book_id).exists())


# --- F_Search_1, F_Search_2: Поиск книг ---

class BookSearchAPITest(TestCase):
    """F_Search_1, F_Search_2: Поиск книг по названию и фильтр по жанрам."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user('searcher')
        self.client.force_authenticate(user=self.user)
        # Книги разных пользователей
        owner1 = make_user('owner1')
        owner2 = make_user('owner2')
        make_user_book(owner1, make_book('Harry Potter', 'J.K.R.', 'x', 'Fantasy'), location='55.75,37.61')
        make_user_book(owner2, make_book('Harry Potter 2', 'J.K.R.', 'x', 'Fantasy, Adventure'), location='55.75,37.61')
        make_user_book(owner1, make_book('1984', 'Orwell', 'x', 'Dystopia'), location='55.75,37.61')

    def test_search_by_title(self):
        """F_Search_1: Поиск книг по названию среди всех пользователей."""
        resp = self.client.get('/api/books/search/', {'query': 'Harry'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.json().get('results', [])
        self.assertGreaterEqual(len(results), 2)
        names = [r['book']['name'] for r in results]
        self.assertIn('Harry Potter', names)
        self.assertIn('Harry Potter 2', names)

    def test_search_query_too_long(self):
        """F_Search_1: Строка поиска до 50 символов — отклонение при превышении."""
        resp = self.client.get('/api/books/search/', {'query': 'a' * 51})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', resp.json())

    def test_search_filter_by_genres(self):
        """F_Search_2: Фильтрация результатов по жанрам."""
        resp = self.client.get('/api/books/search/', {'query': 'Harry', 'genres': 'Fantasy'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.json().get('results', [])
        for r in results:
            self.assertIn('Fantasy', r['book'].get('genres', []))

    def test_search_filter_by_multiple_genres(self):
        """F_Search_2: Фильтр по нескольким жанрам."""
        resp = self.client.get('/api/books/search/', {'query': 'Harry', 'genres': 'Fantasy,Adventure'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.json().get('results', [])
        self.assertGreaterEqual(len(results), 1)


class BookSuggestionMockAPITest(TestCase):
    """
    Интеграционный тест BookSuggestionView с заглушкой внешнего сервиса Google Books.
    Здесь мы не ходим в реальный интернет, а подменяем HTTP‑ответ через библиотеку responses.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = make_user("google_user")
        self.client.force_authenticate(user=self.user)

    @responses.activate
    def test_suggestions_from_mocked_google_books(self):
        """
        Mock‑сценарий:
        - перехватываем запрос к https://www.googleapis.com/books/v1/volumes
        - возвращаем предсказуемый JSON
        - проверяем маппинг полей и нормализацию жанров.
        """
        query = "PythonTesting"
        google_url = (
            f"https://www.googleapis.com/books/v1/volumes?q={query}&key={settings.GOOGLE_API_KEY}"
        )

        responses.add(
            responses.GET,
            google_url,
            json={
                "items": [
                    {
                        "id": "book-1",
                        "volumeInfo": {
                            "title": "Testing with Python",
                            "authors": ["Alice"],
                            "description": "Great testing book",
                            "categories": ["Computers / Programming"],
                        },
                    }
                ]
            },
            status=200,
        )

        resp = self.client.get("/api/books/suggestions/", {"query": query})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(len(data), 1)
        item = data[0]
        self.assertEqual(item["id"], "book-1")
        self.assertEqual(item["name"], "Testing with Python")
        self.assertEqual(item["author"], "Alice")
        self.assertEqual(item["overview"], "Great testing book")
        # genres нормализуется до последней части после слеша
        self.assertEqual(item["genres"], "Programming")


# --- F_Exchange_1–F_Exchange_9: Обмен книгами ---

class ExchangeRequestCreateAPITest(TestCase):
    """F_Exchange_1: Создание запроса на обмен чужой книги."""

    def setUp(self):
        self.client = APIClient()
        self.owner = make_user('owner')
        self.requester = make_user('requester')
        self.client.force_authenticate(user=self.requester)
        self.ub = make_user_book(self.owner, make_book('Shared Book'), location='55.75,37.61')

    def test_create_exchange_request_success(self):
        """F_Exchange_1: Успешное создание запроса на обмен."""
        resp = self.client.post('/api/exchange-requests/', {'user_book_id': self.ub.user_book_id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.json()
        self.assertEqual(data['status'], 'pending')
        self.assertEqual(data['requester'], 'requester')
        self.assertEqual(data['owner'], 'owner')
        self.assertIn('location', data.get('book', {}))
        self.ub.refresh_from_db()
        self.assertEqual(self.ub.status, 'requested')

    def test_create_exchange_own_book_forbidden(self):
        """F_Exchange_4: Нельзя создать запрос на обмен для собственной книги."""
        self.client.force_authenticate(user=self.owner)
        resp = self.client.post('/api/exchange-requests/', {'user_book_id': self.ub.user_book_id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('own book', resp.json().get('error', '').lower())

    def test_create_exchange_duplicate_pending_forbidden(self):
        """F_Exchange_5: Нельзя создать повторный pending для той же книги."""
        self.client.post('/api/exchange-requests/', {'user_book_id': self.ub.user_book_id}, format='json')
        resp = self.client.post('/api/exchange-requests/', {'user_book_id': self.ub.user_book_id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('active', resp.json().get('error', '').lower())


class ExchangeRequestAcceptRejectAPITest(TestCase):
    """F_Exchange_2: Принятие или отклонение запроса на обмен."""

    def setUp(self):
        self.client = APIClient()
        self.owner = make_user('owner')
        self.requester = make_user('requester')
        self.ub = make_user_book(self.owner, make_book('Book'), location='55.75,37.61')
        self.req = ExchangeRequest.objects.create(
            book=self.ub,
            requester=self.requester,
            owner=self.owner,
            status='pending',
        )
        self.client.force_authenticate(user=self.owner)

    def test_accept_exchange_request(self):
        """F_Exchange_2: Принятие запроса."""
        resp = self.client.patch(
            f'/api/exchange-requests/{self.req.exchange_request_id}/',
            {'action': 'accept'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['status'], 'accepted')
        self.ub.refresh_from_db()
        self.assertEqual(self.ub.status, 'exchanged')

    def test_reject_exchange_request(self):
        """F_Exchange_2: Отклонение запроса."""
        resp = self.client.patch(
            f'/api/exchange-requests/{self.req.exchange_request_id}/',
            {'action': 'reject'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['status'], 'rejected')
        self.ub.refresh_from_db()
        self.assertEqual(self.ub.status, 'available')


class ExchangeRequestListAPITest(TestCase):
    """F_Exchange_3: История запросов на обмен (инициатор или владелец)."""

    def setUp(self):
        self.client = APIClient()
        self.owner = make_user('owner')
        self.requester = make_user('requester')
        self.ub = make_user_book(self.owner, make_book('Book'), location='55.75,37.61')
        self.req = ExchangeRequest.objects.create(
            book=self.ub,
            requester=self.requester,
            owner=self.owner,
            status='pending',
        )

    def test_list_exchanges_as_requester(self):
        """F_Exchange_3: Список обменов для инициатора."""
        self.client.force_authenticate(user=self.requester)
        resp = self.client.get('/api/exchange-requests/list/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        results = data.get('results', data) if isinstance(data, dict) else data
        self.assertGreaterEqual(len(results), 1)

    def test_list_exchanges_as_owner(self):
        """F_Exchange_3: Список обменов для владельца книги."""
        self.client.force_authenticate(user=self.owner)
        resp = self.client.get('/api/exchange-requests/list/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        results = data.get('results', data) if isinstance(data, dict) else data
        self.assertGreaterEqual(len(results), 1)


class ExchangeDeleteWithActiveRequestsTest(TestCase):
    """F_Exchange_6, F_Exchange_7: Удаление книги при активных запросах."""

    def setUp(self):
        self.client = APIClient()
        self.owner = make_user('owner')
        self.requester = make_user('requester')
        self.client.force_authenticate(user=self.owner)
        self.ub = make_user_book(self.owner, make_book('Book'), location='55.75,37.61')
        self.req = ExchangeRequest.objects.create(
            book=self.ub,
            requester=self.requester,
            owner=self.owner,
            status='pending',
        )

    def test_delete_without_confirm_returns_409(self):
        """F_Exchange_6: Без confirm возвращается 409 с активными запросами."""
        resp = self.client.delete(f'/api/books/{self.ub.user_book_id}/')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        data = resp.json()
        self.assertIn('active_requests', data)
        self.assertIn('confirm', data.get('error', '').lower())
        self.assertTrue(UserBook.objects.filter(user_book_id=self.ub.user_book_id).exists())

    def test_delete_with_confirm_succeeds(self):
        """F_Exchange_6, F_Exchange_7: С confirm удаление проходит, статус -> cancelled."""
        resp = self.client.delete(f'/api/books/{self.ub.user_book_id}/?confirm=true')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(UserBook.objects.filter(user_book_id=self.ub.user_book_id).exists())
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, 'cancelled')
        self.assertIsNone(self.req.book_id)


class ExchangeOneSidedAndLocationTest(TestCase):
    """F_Exchange_8, F_Exchange_9: Обмен односторонний, на локации книги."""

    def setUp(self):
        self.client = APIClient()
        self.owner = make_user('owner')
        self.requester = make_user('requester')
        self.client.force_authenticate(user=self.requester)
        self.ub = make_user_book(self.owner, make_book('Book'), condition='OK', location='55.7558,37.6173')

    def test_exchange_is_one_sided_no_reciprocity(self):
        """F_Exchange_8: Обмен односторонний — при создании не требуется книга взамен."""
        resp = self.client.post('/api/exchange-requests/', {'user_book_id': self.ub.user_book_id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.json()
        self.assertNotIn('book_to_give', data)
        self.assertNotIn('exchange_for', data)

    def test_exchange_response_includes_location(self):
        """F_Exchange_9: В ответе запроса на обмен есть локация книги."""
        resp = self.client.post('/api/exchange-requests/', {'user_book_id': self.ub.user_book_id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        book_data = resp.json().get('book', {})
        self.assertIn('location', book_data)
        self.assertEqual(book_data['location'], '55.7558,37.6173')
