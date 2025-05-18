# Book Management API
This project is a RESTful API built with Django and Django REST Framework (DRF) for managing books. Users can add books to a shared library either by fetching book details via the Google Books API or by manually providing book details. The API ensures that books with the same title are not duplicated and associates user-specific book data (e.g., condition, location) with existing book records.

## Prerequisites

- Python 3.8+
- PostgreSQL (or another supported database)
- A Google Books API key

## Installation

1. Clone the Repository:
    ```
    git clone <repository-url>
    cd <repository-directory>
    ```

2. Set Up a Virtual Environment:
    ```
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3. Install Dependencies:
    ```
    pip install django djangorestframework psycopg2-binary requests
    ```

4. Configure Environment Variables:
    Create a .env file in the project root and add your Google Books API key and database settings:
    ```
    GOOGLE_API_KEY=your_google_api_key
    DATABASE_URL=postgres://user:password@localhost:5432/dbname
    ```
   
5. Run Migrations:
    ```
    python manage.py makemigrations
    python manage.py migrate
    ```

6. Create a Superuser:
    ```
    python manage.py createsuperuser
    ```

7. Run the Development Server:
    ```
    python manage.py runserver
    ```

## API Endpoints
1. Obtain Authentication Token (**_User_**)
   - URL: POST /api/token/
   - Body:
    ```
    {
        "username": "root",
        "password": "yourpassword"
    }
    ```
   - Response:
    ```
    {
        "access": "your_access_token",
        "refresh": "your_refresh_token"
    }
    ```

2. Search for Books (Suggestions)

   - URL: _GET /api/books/suggestions/?query=<search_term>_
   - Headers: Authorization: Bearer your_access_token
   - Example:GET /api/books/suggestions/?query=Harry%20Potter
   - Response:
    ```
    [
        {
            "id": "book_id",
            "name": "Harry Potter and the Philosopher's Stone",
            "author": "J.K. Rowling",
            "overview": "A young wizard's journey...",
            "genres": "Fantasy, Adventure"
        },
        ...
    ]
    ```

3. Add a Book (via Google Books API)
   - URL: _POST /api/books/_
   - Headers: Authorization: Bearer your_access_token
   - Body:
    ```
        {
            "book_id": "iO5pApw2JycC",
            "condition": "OK",
            "location": "55.7558,37.6173"
        }
    ```
   - Response:
    ```
   {
        "message": "Book added successfully",
        "book_id": 1
    }
    ```

4. Add a Custom Book
   - URL: POST /api/books/
   - Headers: Authorization: Bearer your_access_token
   - Body:
    ```
    {
        "name": "My Custom Book",
        "author": "John Doe",
        "overview": "This is a custom book description.",
        "genres": "Fiction, Adventure",
        "condition": "OK",
        "location": "55.7558,37.6173"
    }
    ```
   - Response:
    ```
    {
        "message": "Book added successfully",
        "book_id": 2
    }
    ```