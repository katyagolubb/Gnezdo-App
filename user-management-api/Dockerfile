FROM python:3.12-slim

# Установка рабочей директории
WORKDIR /app

# Копирование зависимостей и установка
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY . .

# Сбор статических файлов
RUN python manage.py collectstatic --noinput

# Экспонирование порта
EXPOSE 5001

EXPOSE 8080

# Запуск через Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "4", "--timeout", "120", "config.wsgi:application"]