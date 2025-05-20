# Book Management API
This project is a RESTful API built with Django and Django REST Framework (DRF) for managing books. Users can add books to a shared library either by fetching book details via the Google Books API or by manually providing book details. The API ensures that books with the same title are not duplicated and associates user-specific book data (e.g., condition, location) with existing book records.

## Prerequisites

- Python 3.8+
- PostgreSQL (or another supported database)
- A Google Books API key
- Docker (for Redis caching)
- Cloudinary account (for photo storage)

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
5. Set Up Redis with Docker:
   - Ensure Docker is installed (Docker Desktop).
   - Run Redis container:
       ```bash
       docker run -d -p 6379:6379 --name redis-container redis
       ```
   - Verify Redis is running:
       ```bash
       docker ps
       ```
    or connect and test:
    ```bash
    docker exec -it redis-container redis-cli ping
    ```
    (Should return PONG).

6. Run Migrations:
    ```
    python manage.py makemigrations
    python manage.py migrate
    ```

7. Create a Superuser:
    ```
    python manage.py createsuperuser
    ```

8. Run the Development Server:
    ```
    python manage.py runserver
    ```

## API Endpoints
1. **Obtain Authentication Token (**_User_**)**
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

2. **Search for Books (Suggestions)**
   - URL: GET /api/books/suggestions/?query=<search_term>
   - Example: GET /api/books/suggestions/?query=Harry%20Potter
   - Response:
     ```json
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
3. **CRUD Operations for Books**
- **Create a Book**
  - URL: POST /api/books/
  - Methods: Supports adding via Google Books API or manually.
  - Body (Google Books API):
     ```json
     {
         "book_id": "iO5pApw2JycC",
         "condition": "OK",
         "location": "55.7558,37.6173"
     }
     ```
  - Body (Custom Book):
     ```json
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
     ```json
     {
         "message": "Book added successfully",
         "book_id": <user_book_id>
     }
     ```
- **Read (List User's Books)**
  - URL: GET /api/books/list/
  - Description: Returns a list of books. By default, lists the authenticated user's books. Use ?user_id=<id> to list books of another user. 
  - Example: GET /api/books/list/?user_id=2&page=1
  - Response:
     ```json
     {
    "count": 50,
    "next": "http://localhost:8000/api/books/list/?page=2",
    "previous": null,
    "results": [
        {
            "user_book_id": 1,
            "book": {
                "book_id": 1,
                "name": "My Custom Book",
                "author": "John Doe",
                "overview": "This is a custom book description.",
                "genres": "Fiction, Adventure"
            },
            "condition": "OK",
            "location": "55.7558,37.6173"
        },
        ...
    ]
    }
     ```
- **Read (Retrieve Book Details)**
  - URL: GET /api/books/<user_book_id>/
  - Description: Returns details of a specific book record.
  - Response:
     ```json
     {
         "user_book_id": 1,
         "book": {
             "book_id": 1,
             "name": "My Custom Book",
             "author": "John Doe",
             "overview": "This is a custom book description.",
             "genres": "Fiction, Adventure"
         },
         "condition": "OK",
         "location": "55.7558,37.6173"
     }
     ```
- **Update a Book**
  - URL: PUT /api/books/<user_book_id>/
  - Description: Updates condition and/or location for the user's book (all books for superusers).
  - Body:
     ```json
     {
         "condition": "Excellent",
         "location": "40.7128,-74.0060"
     }
     ```
  - Response:
     ```json
     {
         "message": "Book updated successfully"
     }
     ```
- **Delete a Book**
  - URL: DELETE /api/books/<user_book_id>/
  - Description: Deletes the user's book record (all books for superusers).
  - Response:
     ```json
     {
         "message": "Book deleted successfully"
     }
     ```
4. **Search and Filter Books**
- **Search Books by Title**
  - URL: GET /api/books/search/?query=<search_term>
  - Description: Searches for books by title across all users' records.
  - Example: GET /api/books/search/?query=Harry&page=1
  - Response:
      ```json
      {
    "count": 20,
    "next": "http://localhost:8000/api/books/search/?query=Harry&page=2",
    "previous": null,
    "results": [
        {
            "user_book_id": 1,
            "book": {
                "book_id": 1,
                "name": "Harry Potter and the Philosopher's Stone",
                "author": "J.K. Rowling",
                "overview": "A young wizard's journey...",
                "genres": "Fantasy, Adventure"
            },
            "condition": "OK",
            "location": "55.7558,37.6173"
        },
        ...
    ]
    }
      ```
- **Filter Books by Genres**
  - URL: GET /api/books/search/?query=<search_term>&genres=<genre1>,<genre2>
  - Description: Filters search results by genres (comma-separated).
  - Example: GET /api/books/search/?query=Harry&genres=Fantasy,Adventure&page=1
  - Response:
      ```json
      {
    "count": 15,
    "next": "http://localhost:8000/api/books/search/?query=Harry&genres=Fantasy,Adventure&page=2",
    "previous": null,
    "results": [
        {
            "user_book_id": 1,
            "book": {
                "book_id": 1,
                "name": "Harry Potter and the Philosopher's Stone",
                "author": "J.K. Rowling",
                "overview": "A young wizard's journey...",
                "genres": "Fantasy, Adventure"
            },
            "condition": "OK",
            "location": "55.7558,37.6173"
        },
        ...
    ]
    }
      ```
5. **Photo Management**
- **Upload a Photo**
  - URL: POST /api/books/photos/
  - Description: Uploads a photo for a specific book record. Only the owner of the book can upload photos. Maximum 5 photos per book.
  - Body: Form-data with fields:
    - user_book_id: ID of the UserBook record.
    - file: Image file (JPEG, PNG, or GIF, max 5MB).
  - Example: POST /api/books/photos/ with form-data:
      ```
      user_book_id: 1
      file: (binary image file)
      ```
  - Response:
      ```json
      {
          "photo_id": 1,
          "user_book_id": 1,
          "file_path": "https://res.cloudinary.com/your-cloud-name/image/upload/v1234567890/books/1/sample.jpg"
      }
      ```
- **List Photos**
  - URL: GET /api/books/photos/?user_book_id=<id>
  - Description: Returns a paginated list of photo URLs for a specific book record. Any authenticated user can view photos.
  - Example: GET /api/books/photos/?user_book_id=1
  - Response:
      ```json
      [
          {
              "photo_id": 1,
              "user_book_id": 1,
              "file_path": "https://res.cloudinary.com/your-cloud-name/image/upload/v1234567890/books/1/sample.jpg"
          },
          ...
      ]
      ```
- **Update a Photo**
  - URL: PATCH /api/books/photos/<photo_id>/
  - Description: Replaces an existing photo with a new one. Only the owner of the book can update photos.
  - Body: Form-data with field:
    - file: New image file (JPEG, PNG, or GIF, max 5MB).
  - Example: PATCH /api/books/photos/1/ with form-data:
      ```
      user_book_id: 1
      file: (binary image file)
      ```
  - Response:
      ```json
      {
          "photo_id": 1,
          "user_book_id": 1,
          "file_path": "https://res.cloudinary.com/your-cloud-name/image/upload/v1234567891/books/1/new-sample.jpg"
      }
      ```
- **Delete a Photo**
  - URL: DELETE /api/books/photos/<photo_id>/
  - Description: Deletes a photo record and the file from Cloudinary. Only the owner of the book can delete photos.
  - Example: DELETE /api/books/photos/1/
  - Response:
      ```json
      {
          "message": "Photo deleted successfully"
      }
      ```