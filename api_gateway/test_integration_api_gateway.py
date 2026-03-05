"""
Интеграционные E2E‑тесты для API Gateway.

Все тесты выполняют реальные HTTP‑запросы к запущенным в Docker
микросервисам через API Gateway (порт 8000). Взаимодействие внутренних
сервисов НЕ мокается, моками/обходом внешних зависимостей мы пользуемся
только косвенно, выбирая сценарии, не требующие Google Books, Cloudinary и т.п.
"""

import uuid
from typing import Dict, Any, List

import pytest
import requests
import respx
from fastapi.testclient import TestClient
from httpx import Response as HTTPXResponse

from main import app


GATEWAY_URL = "http://api_gateway:8000"


def _unique(name: str) -> str:
    """Генерация уникального суффикса для пользователей/объектов."""
    return f"{name}_{uuid.uuid4().hex[:8]}"


def register_user(username: str) -> Dict[str, Any]:
    """
    Регистрация пользователя через API Gateway.
    Задействованные сервисы/модули:
    - api_gateway (маршрутизация /api/users/register/ → user-management)
    - user-management-api (accounts.views.register, accounts.serializers.UserSerializer)
    - PostgreSQL (БД пользователей)
    """
    payload = {
        "username": username,
        "email": f"{username}@example.com",
        "password": "Password123",
    }
    resp = requests.post(f"{GATEWAY_URL}/api/users/register/", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def obtain_token(username: str) -> str:
    """
    Получение JWT‑токена через API Gateway.
    Взаимодействие:
    - api_gateway (/api/users/token)
    - user-management-api (JWT‑аутентификация)
    """
    resp = requests.post(
        f"{GATEWAY_URL}/api/users/token",
        json={"username": username, "password": "Password123"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data["access"]


def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_book(token: str, title: str) -> Dict[str, Any]:
    """
    Создание книги (ручной ввод, без Google Books).
    Взаимодействие:
    - api_gateway (/api/books)
    - book-api (books.views.BookCreateView, models Book/UserBook)
    - user-management-api (проверка JWT)
    - PostgreSQL (БД книг и пользовательских экземпляров)
    """
    payload = {
        "name": title,
        "author": "John Doe",
        "overview": "Test book",
        "genres": "Fiction",
        "condition": "OK",
        "location": "55.7558,37.6173",
    }
    resp = requests.post(
        f"{GATEWAY_URL}/api/books",
        headers=auth_headers(token),
        json=payload,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def list_own_books(token: str) -> List[Dict[str, Any]]:
    resp = requests.get(
        f"{GATEWAY_URL}/api/books/list",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["results"]


@pytest.mark.integration
def test_registration_and_duplicate_username():
    """
    Кейс 1: регистрация и повторная регистрация с тем же username.

    Проверяем взаимодействие:
    - API Gateway ↔ User Management API ↔ PostgreSQL (модель User, валидация уникальности).
    """
    username = _unique("alice")

    # Первая регистрация — успех
    first = register_user(username)
    assert first["username"] == username

    # Вторая с тем же username — 400 ошибка валидации
    payload = {
        "username": username,
        "email": f"{username}_dup@example.com",
        "password": "Password123",
    }
    resp = requests.post(f"{GATEWAY_URL}/api/users/register/", json=payload)
    assert resp.status_code == 400
    body = resp.json()
    assert any("существует" in str(err) for err in body.get("username", []) or [])


@pytest.mark.integration
def test_token_and_get_current_user_profile():
    """
    Кейс 2: получение JWT‑токена и профиля текущего пользователя.

    Взаимодействие:
    - API Gateway (/api/users/token, /api/users/me)
    - User Management API (аутентификация, endpoint профиля)
    - PostgreSQL (чтение пользователя).
    """
    username = _unique("bob")
    register_user(username)

    token = obtain_token(username)

    resp = requests.get(f"{GATEWAY_URL}/api/users/me", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["username"] == username


@pytest.mark.integration
def test_unauthorized_books_list_returns_401():
    """
    Кейс 3: попытка получить список книг без авторизации.

    Взаимодействие:
    - API Gateway → Book API (books.views.UserBookListView) с провалом на уровне DRF/permission.
    """
    resp = requests.get(f"{GATEWAY_URL}/api/books/list")
    assert resp.status_code in (401, 403)


@pytest.mark.integration
def test_create_book_and_list_own_books():
    """
    Кейс 4: пользователь добавляет книгу и видит её в своём списке.

    Взаимодействие:
    - API Gateway (/api/users/register/, /api/users/token, /api/books, /api/books/list)
    - User Management API (регистрация, JWT)
    - Book API (создание UserBook и выборка по пользователю)
    - PostgreSQL (сохранение и чтение записей).
    """
    username = _unique("carol")
    register_user(username)
    token = obtain_token(username)

    title = _unique("My Test Book")
    create_book(token, title)

    books = list_own_books(token)
    assert any(b["book"]["name"] == title for b in books)


@pytest.mark.integration
def test_search_books_by_title_via_gateway():
    """
    Кейс 5: поиск книги по названию.

    Взаимодействие:
    - API Gateway (/api/books/search/)
    - Book API (books.views.BookSearchView + ORM)
    - PostgreSQL (фильтрация по названию).
    """
    username = _unique("dave")
    register_user(username)
    token = obtain_token(username)

    title = _unique("UniqueTitle")
    create_book(token, title)

    resp = requests.get(
        f"{GATEWAY_URL}/api/books/search/",
        headers=auth_headers(token),
        params={"query": title[:10]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert any(item["book"]["name"] == title for item in data["results"])


@pytest.mark.integration
def test_exchange_request_full_flow_accept():
    """
    Кейс 6: полный сценарий обмена — запрос и принятие.

    Взаимодействие:
    - API Gateway (/api/users/*, /api/books, /api/books/list, /api/exchange-requests, /api/exchange-requests/{id})
    - User Management API (двое пользователей, JWT)
    - Book API (создание UserBook, ExchangeRequestView/ExchangeRequestDetailView)
    - PostgreSQL (связанные таблицы пользователей, книг, запросов на обмен).
    """
    owner_name = _unique("owner")
    requester_name = _unique("requester")
    register_user(owner_name)
    register_user(requester_name)

    owner_token = obtain_token(owner_name)
    requester_token = obtain_token(requester_name)

    # Владелец создаёт книгу
    title = _unique("ExchangeBook")
    create_book(owner_token, title)
    owner_books = list_own_books(owner_token)
    user_book_id = next(b["user_book_id"] for b in owner_books if b["book"]["name"] == title)

    # Инициатор создаёт запрос на обмен
    resp = requests.post(
        f"{GATEWAY_URL}/api/exchange-requests",
        headers=auth_headers(requester_token),
        json={"user_book_id": user_book_id},
    )
    assert resp.status_code == 201, resp.text
    exch = resp.json()
    assert exch["status"] == "pending"
    exchange_id = exch["exchange_request_id"]

    # Владелец принимает запрос
    resp = requests.patch(
        f"{GATEWAY_URL}/api/exchange-requests/{exchange_id}",
        headers=auth_headers(owner_token),
        json={"action": "accept"},
    )
    assert resp.status_code == 200, resp.text
    exch_after = resp.json()
    assert exch_after["status"] == "accepted"


@pytest.mark.integration
def test_exchange_request_own_book_forbidden():
    """
    Кейс 7: пользователь пытается запросить свою же книгу.

    Взаимодействие:
    - API Gateway (/api/books, /api/books/list, /api/exchange-requests)
    - Book API (ExchangeRequestView с проверкой владельца)
    - User Management API (аутентификация)
    - PostgreSQL (проверка связей User–UserBook).
    """
    username = _unique("selfowner")
    register_user(username)
    token = obtain_token(username)

    title = _unique("OwnBook")
    create_book(token, title)
    books = list_own_books(token)
    user_book_id = next(b["user_book_id"] for b in books if b["book"]["name"] == title)

    resp = requests.post(
        f"{GATEWAY_URL}/api/exchange-requests",
        headers=auth_headers(token),
        json={"user_book_id": user_book_id},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert "You cannot request your own book" in body.get("error", "")


@pytest.mark.integration
def test_delete_book_with_pending_exchange_requires_confirm():
    """
    Кейс 8: удаление книги с активными запросами на обмен требует подтверждения.

    Взаимодействие:
    - API Gateway (/api/books, /api/books/list, /api/exchange-requests, DELETE /api/books/{id})
    - Book API (UserBookDetailView.delete с проверкой активных ExchangeRequest)
    - User Management API (JWT)
    - PostgreSQL (UserBook, ExchangeRequest).
    """
    owner_name = _unique("owner2")
    requester_name = _unique("requester2")
    register_user(owner_name)
    register_user(requester_name)

    owner_token = obtain_token(owner_name)
    requester_token = obtain_token(requester_name)

    title = _unique("DeletableBook")
    create_book(owner_token, title)
    owner_books = list_own_books(owner_token)
    user_book_id = next(b["user_book_id"] for b in owner_books if b["book"]["name"] == title)

    # Создаём pending‑запрос
    resp = requests.post(
        f"{GATEWAY_URL}/api/exchange-requests",
        headers=auth_headers(requester_token),
        json={"user_book_id": user_book_id},
    )
    assert resp.status_code == 201, resp.text

    # Пытаемся удалить без confirm=true
    resp = requests.delete(
        f"{GATEWAY_URL}/api/books/{user_book_id}",
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert "active_requests" in body


@pytest.mark.integration
def test_update_user_profile_through_gateway():
    """
    Кейс 9: обновление профиля пользователя.

    Взаимодействие:
    - API Gateway (/api/users/update, /api/users/me)
    - User Management API (accounts.views.update, UserUpdateSerializer)
    - PostgreSQL (обновление полей пользователя).
    """
    username = _unique("updateuser")
    register_user(username)
    token = obtain_token(username)

    new_email = f"{username}_new@example.com"
    resp = requests.put(
        f"{GATEWAY_URL}/api/users/update",
        headers=auth_headers(token),
        json={"email": new_email},
    )
    assert resp.status_code == 200, resp.text

    resp = requests.get(f"{GATEWAY_URL}/api/users/me", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == new_email


@pytest.mark.integration
def test_get_other_user_public_profile():
    """
    Кейс 10: получение публичного профиля другого пользователя.

    Взаимодействие:
    - API Gateway (/api/users/{id})
    - User Management API (публичный профиль пользователя)
    - PostgreSQL (чтение другого пользователя).
    """
    user1 = _unique("user1")
    user2 = _unique("user2")
    u1 = register_user(user1)
    register_user(user2)

    token2 = obtain_token(user2)

    resp = requests.get(
        f"{GATEWAY_URL}/api/users/{u1['id']}",
        headers=auth_headers(token2),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["username"] == user1


@pytest.mark.integration
@respx.mock
def test_book_suggestions_via_gateway_with_mocked_book_service():
    """
    Кейс 11 (с заглушкой внешнего сервиса):

    Пользователь запрашивает подсказки книг через API Gateway, а внутренний
    вызов в Book API подменяется мок‑сервисом. Так мы изолируемся от
    настоящего Book API (и тем более от Google Books), но при этом тестируем
    сам Gateway и его маршрутизацию.
    """
    client = TestClient(app)

    query = "PythonTesting"

    # Gateway внутри ходит в Book API по URL:
    #   http://book-api:5000/api/books/suggestions/
    # подменяем этот вызов с помощью respx (mock для httpx).
    upstream = respx.get("http://book-api:5000/api/books/suggestions/").mock(
        return_value=HTTPXResponse(
            status_code=200,
            json=[
                {
                    "id": "book-1",
                    "name": "Testing with Python",
                    "author": "Alice",
                    "overview": "Great testing book",
                    "genres": "Programming",
                }
            ],
        )
    )

    # 1) "Пользователь" обращается к API Gateway за подсказками.
    resp = client.get("/api/books/suggestions", params={"query": query})
    assert resp.status_code == 200, resp.text

    # 2) Gateway внутри делает HTTP‑запрос в Book API,
    #    но он перехватывается нашей заглушкой (upstream).
    assert upstream.called

    # 3) Пользователь получает данные, которые вернул mock‑Book API,
    #    и мы проверяем, что Gateway корректно их пробросил.
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    item = data[0]
    assert item["id"] == "book-1"
    assert item["name"] == "Testing with Python"
    assert item["author"] == "Alice"

