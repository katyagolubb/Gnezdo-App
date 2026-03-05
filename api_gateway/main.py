from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio
import random
from typing import Optional
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="API Gateway", version="1.0.0")

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Конфигурация микросервисов
SERVICES = {
    "user-management": [
        "http://user-management-api:5001",
        # Добавьте второй экземпляр если нужна балансировка
        # "http://user-management-api_2:5001"
    ],
    "book": [
        "http://book-api:5000",
        # Добавьте второй экземпляр если нужна балансировка
        # "http://book-api_2:5000"
    ],
    "recommendation": [
        "http://recommendation-service:8002",
        # Добавьте второй экземпляр если нужна балансировка
        # "http://recommendation-service_2:8002"
    ]
}

# Простая балансировка нагрузки (round-robin)
service_counters = {service: 0 for service in SERVICES}


def get_service_url(service_name: str) -> str:
    """Получает URL сервиса с простой балансировкой нагрузки"""
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")

    urls = SERVICES[service_name]
    if not urls:
        raise HTTPException(status_code=503, detail=f"No available instances for {service_name}")

    # Round-robin балансировка
    counter = service_counters[service_name]
    url = urls[counter % len(urls)]
    service_counters[service_name] = (counter + 1) % len(urls)

    return url


async def forward_request(
    service_name: str,
    path: str,
    method: str,
    headers: dict,
    params: dict = None,
    json_data: dict = None,
    form_data=None
):
    """Пересылает запрос в микросервис"""
    service_url = get_service_url(service_name)
    url = f"{service_url}/api{path}"
    logger.info(f"Forwarding {method} request to {url} with headers {headers} and params {params}")

    filtered_headers = {k: v for k, v in headers.items() if k.lower() not in ['host', 'content-length', 'connection']}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method in ["POST", "PATCH"] and form_data:
                response = await client.request(method.lower(), url, headers=filtered_headers, files=form_data)
            else:
                if method == "GET":
                    response = await client.get(url, headers=filtered_headers, params=params)
                elif method == "POST":
                    response = await client.post(url, headers=filtered_headers, json=json_data, params=params)
                elif method == "PUT":
                    response = await client.put(url, headers=filtered_headers, json=json_data, params=params)
                elif method == "PATCH":
                    response = await client.patch(url, headers=filtered_headers, json=json_data, params=params)
                elif method == "DELETE":
                    response = await client.delete(url, headers=filtered_headers, params=params)
                else:
                    logger.error(f"Unsupported method: {method}")
                    raise HTTPException(status_code=405, detail="Method not allowed")

            logger.info(f"Response from {url}: status={response.status_code}, content={response.content}, headers={response.headers}")
            return response

    except httpx.RequestError as e:
        logger.error(f"Request to {service_name} failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service {service_name} unavailable")
    except httpx.TimeoutException:
        logger.error(f"Timeout calling {service_name}")
        raise HTTPException(status_code=504, detail=f"Service {service_name} timeout")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "services": list(SERVICES.keys())}


# ============= USER MANAGEMENT ROUTES =============

@app.post("/api/users/register/")
async def register_user(request: Request):
    """Регистрация пользователя"""
    json_data = await request.json()
    headers = dict(request.headers)

    response = await forward_request("user-management", "/register/", "POST", headers, json_data=json_data)

    # Пробрасываем JSON-ответ сервиса как есть (включая ошибки валидации по полям).
    # Если вдруг пришёл не-JSON, возвращаем текст как detail.
    try:
        content = response.json()
        return JSONResponse(content=content, status_code=response.status_code)
    except ValueError:
        logger.error(
            "Non-JSON response from user-management: "
            f"status={response.status_code}, content={response.content}"
        )
        return JSONResponse(
            content={"detail": response.text or "Invalid response from user-management service"},
            status_code=response.status_code if response.status_code >= 400 else 502,
        )


@app.post("/api/users/token")
async def get_token(request: Request):
    """Получение JWT токена"""
    json_data = await request.json()
    headers = dict(request.headers)

    response = await forward_request("user-management", "/token/", "POST", headers, json_data=json_data)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.post("/api/users/token/refresh")
async def refresh_token(request: Request):
    """Обновление JWT токена"""
    json_data = await request.json()
    headers = dict(request.headers)

    response = await forward_request("user-management", "/token/refresh/", "POST", headers, json_data=json_data)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.get("/api/users/me")
async def get_user_profile(request: Request):
    """Получение профиля текущего пользователя"""
    headers = dict(request.headers)

    response = await forward_request("user-management", "/me/", "GET", headers)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.put("/api/users/update")
async def update_user(request: Request):
    """Обновление данных пользователя"""
    json_data = await request.json()
    headers = dict(request.headers)

    response = await forward_request("user-management", "/update/", "PUT", headers, json_data=json_data)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.delete("/api/users/delete")
async def delete_user(request: Request):
    """Удаление пользователя"""
    headers = dict(request.headers)

    response = await forward_request("user-management", "/delete/", "DELETE", headers)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.get("/api/users/{user_id}")
async def get_user_by_id(user_id: int, request: Request):
    """Получение данных пользователя по ID"""
    headers = dict(request.headers)

    response = await forward_request("user-management", f"/users/{user_id}/", "GET", headers)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.post("/api/users/password-reset")
async def password_reset_request(request: Request):
    """Запрос сброса пароля"""
    json_data = await request.json()
    headers = dict(request.headers)

    response = await forward_request("user-management", "/password-reset/", "POST", headers, json_data=json_data)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.post("/api/users/password-reset/confirm")
async def password_reset_confirm(request: Request):
    """Подтверждение сброса пароля"""
    json_data = await request.json()
    headers = dict(request.headers)

    response = await forward_request("user-management", "/password-reset/confirm/", "POST", headers,
                                     json_data=json_data)
    return JSONResponse(content=response.json(), status_code=response.status_code)


# ============= BOOK SERVICE ROUTES =============

@app.get("/api/books/suggestions")
async def get_book_suggestions(request: Request):
    """Получение предложений книг из Google Books API"""
    headers = dict(request.headers)
    params = dict(request.query_params)

    response = await forward_request("book", "/books/suggestions/", "GET", headers, params=params)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.post("/api/books")
async def create_book(request: Request):
    """Создание книги"""
    json_data = await request.json()
    headers = dict(request.headers)

    response = await forward_request("book", "/books/", "POST", headers, json_data=json_data)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.get("/api/books/list")
async def get_user_books(request: Request):
    """Получение списка книг пользователя"""
    headers = dict(request.headers)
    params = dict(request.query_params)

    response = await forward_request("book", "/books/list/", "GET", headers, params=params)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.get("/api/books/{user_book_id}")
async def get_book_detail(user_book_id: int, request: Request):
    """Получение детальной информации о книге"""
    headers = dict(request.headers)

    response = await forward_request("book", f"/books/{user_book_id}/", "GET", headers)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.put("/api/books/{user_book_id}")
async def update_book(user_book_id: int, request: Request):
    """Обновление книги"""
    json_data = await request.json()
    headers = dict(request.headers)

    response = await forward_request("book", f"/books/{user_book_id}/", "PUT", headers, json_data=json_data)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.delete("/api/books/{user_book_id}")
async def delete_book(user_book_id: int, request: Request):
    """Удаление книги"""
    headers = dict(request.headers)

    response = await forward_request("book", f"/books/{user_book_id}/", "DELETE", headers)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.get("/api/books/search/")
async def search_books(request: Request):
    """Поиск книг по запросу"""
    headers = dict(request.headers)
    params = dict(request.query_params)  # Получаем query и page из параметров
    response = await forward_request("book", "/books/search/", "GET", headers, params=params)

    if response.status_code >= 400:
        logger.error(f"Error from book service: status={response.status_code}, content={response.content}")
        return JSONResponse(
            content={"detail": response.text or "Error from book service"},
            status_code=response.status_code
        )

    try:
        content = response.json()
    except ValueError:
        logger.error(f"Invalid JSON response from book service: {response.content}")
        return JSONResponse(
            content={"detail": "Invalid response from book service"},
            status_code=500
        )

    return JSONResponse(content=content, status_code=response.status_code)


@app.get("/api/books/all")
async def get_all_books(request: Request):
    """Получение всех книг (только для админов)"""
    headers = dict(request.headers)

    response = await forward_request("book", "/books/all/", "GET", headers)
    return JSONResponse(content=response.json(), status_code=response.status_code)


# ============= PHOTO ROUTES =============

@app.post("/api/books/photos/")
async def upload_photo(id: int = Form(...), file: UploadFile = File(...), request: Request = None):
    """Загрузка фото книги"""
    headers = dict(request.headers) if request else {}

    # Подготовка form-data для httpx
    form_data = {
        "user_book_id": (None, str(id)),  # Переименовываем 'id' в 'user_book_id' для соответствия сериализатору
        "file": (file.filename, file.file, file.content_type),
    }

    response = await forward_request("book", "/books/photos/", "POST", headers, form_data=form_data)

    if response.status_code >= 400:
        logger.error(f"Error from book service: status={response.status_code}, content={response.content}")
        return JSONResponse(
            content={"detail": response.text or "Error from book service"},
            status_code=response.status_code
        )

    try:
        content = response.json()
    except ValueError:
        logger.error(f"Invalid JSON response from book service: {response.content}")
        return JSONResponse(
            content={"detail": "Invalid response from book service"},
            status_code=500
        )

    return JSONResponse(content=content, status_code=response.status_code)


@app.get("/api/books/photos/")
async def get_photos(
        request: Request,
        user_book_id: int = Query(..., description="ID of the UserBook to fetch photos for")
):
    """Получение пагинированного списка фотографий для UserBook"""
    headers = dict(request.headers)
    params = {
        "user_book_id": user_book_id
    }

    response = await forward_request("book", "/books/photos/", "GET", headers, params=params)

    if response.status_code >= 400:
        logger.error(f"Error from book service: status={response.status_code}, content={response.content}")
        return JSONResponse(
            content={"detail": response.text or "Error from book service"},
            status_code=response.status_code
        )

    try:
        content = response.json()
    except ValueError:
        logger.error(f"Invalid JSON response from book service: {response.content}")
        return JSONResponse(
            content={"detail": "Invalid response from book service"},
            status_code=500
        )

    return JSONResponse(content=content, status_code=response.status_code)

@app.delete("/api/books/photos/{photo_id}")
async def delete_photo(photo_id: int, request: Request):
    """Удаление фото"""
    headers = dict(request.headers)

    response = await forward_request("book", f"/books/photos/{photo_id}/", "DELETE", headers)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.patch("/api/books/photos/{photo_id}")
async def update_photo(
        photo_id: int,
        user_book_id: int = Form(...),  # Добавляем user_book_id как параметр формы
        file: UploadFile = File(...),
        request: Request = None
):
    """Обновление фото книги"""
    headers = dict(request.headers) if request else {}

    # Логируем входные данные
    logger.info(
        f"Received PATCH request for photo_id={photo_id}, user_book_id={user_book_id}, filename={file.filename}, content_type={file.content_type}")

    # Читаем содержимое файла в память, чтобы избежать проблем с потоком
    file_content = await file.read()
    logger.info(f"File content length: {len(file_content)} bytes")

    # Формируем form-data с user_book_id и файлом
    form_data = {
        "user_book_id": (None, str(user_book_id)),  # Передаем user_book_id как текстовое поле
        "file": (file.filename, file_content, file.content_type),
    }

    response = await forward_request("book", f"/books/photos/{photo_id}/", "PATCH", headers, form_data=form_data)

    if response.status_code >= 400:
        logger.error(f"Error from book service: status={response.status_code}, content={response.content}")
        return JSONResponse(
            content={"detail": response.text or "Error from book service"},
            status_code=response.status_code
        )

    try:
        content = response.json()
    except ValueError:
        logger.error(f"Invalid JSON response from book service: {response.content}")
        return JSONResponse(
            content={"detail": "Invalid response from book service"},
            status_code=500
        )

    return JSONResponse(content=content, status_code=response.status_code)


# ============= EXCHANGE ROUTES =============

@app.post("/api/exchange-requests")
async def create_exchange_request(request: Request):
    """Создание запроса на обмен"""
    json_data = await request.json()
    headers = dict(request.headers)

    response = await forward_request("book", "/exchange-requests/", "POST", headers, json_data=json_data)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.patch("/api/exchange-requests/{exchange_request_id}")
async def handle_exchange_request(exchange_request_id: int, request: Request):
    """Принятие или отклонение запроса на обмен"""
    json_data = await request.json()
    headers = dict(request.headers)

    response = await forward_request("book", f"/exchange-requests/{exchange_request_id}/", "PATCH", headers,
                                     json_data=json_data)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.get("/api/exchange-requests/list")
async def get_user_exchanges(request: Request):
    """Получение списка обменов пользователя"""
    headers = dict(request.headers)

    response = await forward_request("book", "/exchange-requests/list/", "GET", headers)
    return JSONResponse(content=response.json(), status_code=response.status_code)


@app.post("/api/books/owners")
async def get_book_owners(request: Request):
    """Получение владельцев книг"""
    json_data = await request.json()
    headers = dict(request.headers)

    response = await forward_request("book", "/books/owners/", "POST", headers, json_data=json_data)
    return JSONResponse(content=response.json(), status_code=response.status_code)


# ============= RECOMMENDATION SERVICE ROUTES =============

@app.get("/api/recommendations/")
async def get_recommendations(request: Request):
    """Получение рекомендаций"""
    headers = dict(request.headers)
    params = dict(request.query_params)

    response = await forward_request("recommendation", "/recommendations/", "GET", headers, params=params)

    if response.status_code >= 400:
        logger.error(f"Error from recommendation service: status={response.status_code}, content={response.content}")
        return JSONResponse(
            content={"detail": response.text or "Error from recommendation service"},
            status_code=response.status_code
        )

    try:
        content = response.json()
    except ValueError:
        logger.error(f"Invalid JSON response from recommendation service: {response.content}")
        return JSONResponse(
            content={"detail": "Invalid response from recommendation service"},
            status_code=500
        )

    return JSONResponse(content=content, status_code=response.status_code)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)