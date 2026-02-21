# Покрытие тестами по проекту

Проект состоит из нескольких сервисов. Покрытие считается **отдельно по каждому сервису**, затем можно свести цифры в общую таблицу.

---

## 1. User Management API (Django)

**Запуск тестов с отчётом о покрытии (через Docker):**

```bash
# Из корня Gnezdo-App
docker-compose run --rm user-management-api sh -c "coverage run manage.py test accounts && coverage report"
```

**Только процент в последней строке:**

```bash
docker-compose run --rm user-management-api sh -c "coverage run manage.py test accounts && coverage report" | tail -1
```

**HTML-отчёт** (просмотр по файлам и строкам):

```bash
docker-compose run --rm user-management-api sh -c "coverage run manage.py test accounts && coverage html"
# Отчёт будет в контейнере; скопировать на хост:
docker cp $(docker-compose ps -q user-management-api 2>/dev/null || echo "gnezdo-app-user-management-api-run-1"):/app/htmlcov ./user-management-api/htmlcov 2>/dev/null || true
# Или после run сохранить образ и копировать из последнего контейнера
```

**Локально** (если не используете Docker):

```bash
cd user-management-api
pip install -r requirements.txt
coverage run manage.py test accounts
coverage report
coverage html   # htmlcov/index.html
```

---

## 2. Book API (Django)

**Через Docker:**

```bash
docker-compose run --rm book-api sh -c "coverage run manage.py test books && coverage report"
```

**Только итоговая строка с процентом:**

```bash
docker-compose run --rm book-api sh -c "coverage run manage.py test books && coverage report" | tail -1
```

Подробнее: см. `book-api/TESTING.md`.

---

## 3. Recommendation Service (FastAPI)

Сервис использует **FastAPI** (не Django), поэтому тесты запускаются через `unittest`, а не `manage.py test`.

**Единообразный запуск** (как у Django — через один скрипт):

```powershell
# Через Docker (после пересборки: docker-compose build recommendation-service)
docker-compose run --rm recommendation-service python run_tests.py

# Локально
cd recommendation-service
python run_tests.py
```

**С покрытием (Docker):**

```bash
docker-compose run --rm recommendation-service sh -c "coverage run -m unittest discover && coverage report"
```

**С покрытием (локально):**

```bash
cd recommendation-service
pip install -r requirements.txt
coverage run -m unittest discover
coverage report
```

---

## 4. Общий процент покрытия по всему проекту

Запуск скрипта из корня проекта:

```powershell
powershell -File scripts\coverage_all.ps1
```

Скрипт:
1. Запускает coverage для каждого сервиса
2. Выводит отчёт по каждому
3. Считает **общий процент покрытия** как (покрытые строки / всего строк) × 100 по всем сервисам

---

## 5. Итоговая таблица

| Сервис                  | Запуск тестов | Покрытие |
|-------------------------|---------------|----------|
| **user-management-api** | `docker-compose run --rm user-management-api sh -c "python manage.py test accounts"` | `coverage run manage.py test accounts && coverage report` |
| **book-api**            | `docker-compose run --rm book-api sh -c "python manage.py test books"` | `coverage run manage.py test books && coverage report` |
| **recommendation-service** | `docker-compose run --rm recommendation-service python run_tests.py` | `coverage run -m unittest discover && coverage report` |

**Примечание:** recommendation-service использует FastAPI (не Django), поэтому вместо `manage.py test` используется `run_tests.py` или `python -m unittest discover`.
