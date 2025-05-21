# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код проекта
COPY . .

# Указываем порт
EXPOSE 8000

# Команда для запуска
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "api_gateway.wsgi:application"]