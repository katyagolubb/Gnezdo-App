# Gnezdo
## Prerequisites
- Python 3.12+
- PostgreSQL
- Git
- Cloudinary account (for photo uploads)
## Setup
1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/your-repo.git
   cd your-repo
   ```
2. **Create and activate a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```
3. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4. Set up PostgreSQL:
- Create a database named myapp:
    ```bash
    psql -U postgres -c "CREATE DATABASE myapp;"
    ```
- Create a .env file in the project root:
    ```env
    SECRET_KEY=your-secret-key
    DB_NAME=myapp
    DB_USER=postgres
    DB_PASSWORD=your_password
    DB_HOST=localhost
    DB_PORT=5432
    ```
5. **Run migrations:**
    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```
6. **Create a superuser:**
    ```bash
    python manage.py createsuperuser
    ```
7. **Run the development server:**
    ```bash
    python manage.py runserver
    ```
8. **Test the API:**
- Register a user: Send a POST request to http://localhost:8000/api/register/:
    ```json
    {
        "username": "testuser",
        "email": "test@example.com",
        "password": "securepassword123",
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+79991234567",
        "photo": "(upload a file via multipart/form-data)"
    }
    ```
- Obtain Authentication Token: POST http://localhost:8001/api/token/
    ```json
    {
        "username": "testuser",
        "password": "securepassword123"
    }
    ```
    ```json
    {
        "access": "your_access_token",
        "refresh": "your_refresh_token"
    }
    ```
- Get Current User Data: GET http://localhost:8000/api/me/ (requires authentication):
    ```json
    {
        "id": 1,
        "username": "testuser",
        "email": "test@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+79991234567",
        "photo": "image/upload/v1747851859/users/example.jpg"
    }
    ```
- Get Other User Data: GET http://localhost:8000/api/users/<id>/ (requires authentication):
    ```json
    {
        "id": 1,
        "username": "testuser",
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+79991234567",
        "photo": "image/upload/v1747851859/users/example.jpg"
    }
    ```
- Update User Data: PUT http://localhost:8000/api/update/ (requires authentication)
    ```json
    {
        "username": "newusername",
        "email": "newemail@example.com"
    }
    ```
- Request Password Reset: POST http://localhost:8000/api/password-reset/
    ```json
    {
        "email": "test@example.com"
    }
    ```
- Confirm Password Reset: POST http://localhost:8000/api/password-reset/confirm/
    ```json
    {
        "new_password": "newsecurepassword456",
        "uidb64": "MQ",
        "token": "abc123"
    }
    ```
- Delete User: DELETE http://localhost:8000/api/delete/ (requires authentication)

## Admin Panel
- Access the admin panel at http://localhost:8000/admin/.