import requests
from django.http import HttpResponse

# Список экземпляров микросервисов
SERVERS = {
"book": ["http://load-balancer:8000/book/"],
"user": ["http://load-balancer:8000/user/"],
}


def route_request(request, service):
    if service not in SERVERS:
        return HttpResponse("Service not found", status=404)

    target_server = random.choice(SERVERS[service])
    # Простая балансировка round-robin
    try:
        # Перенаправляем запрос к выбранному микросервису
        response = requests.get(f"{target_server}/{request.path}", params=request.GET, timeout=10)
        return HttpResponse(response.text, status=response.status_code)
    except requests.RequestException as e:
        return HttpResponse(f"Error routing to service: {str(e)}", status=500)