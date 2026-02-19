# Тестирование book-api

## Запуск тестов

### Через Docker (рекомендуется)

```bash
# Из корня проекта Gnezdo-App
docker-compose exec book-api python manage.py test books.tests
```

С подробным выводом:

```bash
docker-compose exec book-api python manage.py test books.tests -v 2
```

### Локально (с venv)

```bash
cd book-api
source .venv/bin/activate  # или .venv\Scripts\activate на Windows
pip install -r requirements.txt
python manage.py test books.tests
```

---

## Покрытие кода тестами (Coverage)

### Установка

`coverage` уже добавлен в `requirements.txt`.

### Запуск с отчётом о покрытии

```bash
# Через Docker
docker-compose exec book-api coverage run manage.py test books.tests
docker-compose exec book-api coverage report

# Или одной командой
docker-compose exec book-api sh -c "coverage run manage.py test books.tests && coverage report"
```

### HTML-отчёт (удобно для просмотра)

```bash
docker-compose exec book-api sh -c "coverage run manage.py test books.tests && coverage html"
```

Затем откройте `book-api/htmlcov/index.html` в браузере (файл создаётся внутри контейнера; чтобы увидеть его на хосте, можно скопировать: `docker cp gnezdo-app-book-api-1:/app/htmlcov ./book-api/`).

### Локально

```bash
cd book-api
coverage run manage.py test books.tests
coverage report
coverage html   # создаёт htmlcov/
```

---

## Покрытие функциональных требований

| Требование | Описание | Тесты |
|------------|----------|-------|
| **F1** | Добавление книги (вручную / из выбора) | `BookCreateAPITest`, `BookCreateSerializerTest`, `UserBookCreateSerializerTest` |
| **F2** | Список своих книг | `UserBookListAPITest.test_list_own_books`, `test_list_own_books_empty` |
| **F3** | Список книг другого пользователя | `UserBookListAPITest.test_list_another_user_books`, `test_list_another_user_nonexistent` |
| **F4** | Детальная информация о книге | `UserBookDetailAPITest` |
| **F5** | Обновление книги | `UserBookUpdateAPITest` |
| **F6** | Удаление книги | `UserBookDeleteAPITest` |
| **F_Search_1** | Поиск по названию (до 50 символов) | `BookSearchAPITest.test_search_by_title`, `test_search_query_too_long` |
| **F_Search_2** | Фильтр по жанрам | `BookSearchAPITest.test_search_filter_by_genres`, `test_search_filter_by_multiple_genres` |
| **F_Exchange_1** | Создание запроса на обмен | `ExchangeRequestCreateAPITest.test_create_exchange_request_success` |
| **F_Exchange_2** | Принятие/отклонение запроса | `ExchangeRequestAcceptRejectAPITest` |
| **F_Exchange_3** | История обменов (инициатор/владелец) | `ExchangeRequestListAPITest` |
| **F_Exchange_4** | Нельзя запросить свою книгу | `ExchangeRequestCreateAPITest.test_create_exchange_own_book_forbidden` |
| **F_Exchange_5** | Нельзя дублировать pending | `ExchangeRequestCreateAPITest.test_create_exchange_duplicate_pending_forbidden` |
| **F_Exchange_6** | Проверка активных запросов перед удалением | `ExchangeDeleteWithActiveRequestsTest.test_delete_without_confirm_returns_409` |
| **F_Exchange_7** | При удалении статус → cancelled | `ExchangeDeleteWithActiveRequestsTest.test_delete_with_confirm_succeeds` |
| **F_Exchange_8** | Обмен односторонний | `ExchangeOneSidedAndLocationTest.test_exchange_is_one_sided_no_reciprocity` |
| **F_Exchange_9** | Обмен на локации книги | `ExchangeOneSidedAndLocationTest.test_exchange_response_includes_location` |
