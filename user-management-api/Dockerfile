FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt . RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput RUN python manage.py makemigrations RUN python manage.py migrate

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]