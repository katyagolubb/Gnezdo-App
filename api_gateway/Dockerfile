FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN mkdir -p staticfiles
RUN python manage.py collectstatic --noinput
RUN python manage.py makemigrations
RUN python manage.py migrate

RUN pip install uvicorn

EXPOSE 8000
CMD ["uvicorn", "api_gateway.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]