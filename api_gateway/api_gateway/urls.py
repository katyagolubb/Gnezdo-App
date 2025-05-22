from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

def default_view(request):
    return HttpResponse("Welcome to API Gateway. Use /api/user/ or /api/book/ for routing.", status=200)

try:
    urlpatterns = [
        path('admin/', admin.site.urls),
        path('api/', include('myapp.urls')),
        path('', default_view),
    ]
except ImportError as e:
    # Логирование ошибки импорта для диагностики
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to import myapp.urls: {e}")
    urlpatterns = [
        path('', lambda r: HttpResponse(f"Error: {e}", status=500)),
    ]