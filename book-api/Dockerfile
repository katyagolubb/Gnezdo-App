FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p staticfiles
RUN python manage.py collectstatic --noinput


CMD ["gunicorn", "--bind", "0.0.0.0:5000", "book_microservice.wsgi:application"]