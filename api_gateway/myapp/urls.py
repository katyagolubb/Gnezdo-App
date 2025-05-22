from django.urls import path
from . import views

urlpatterns = [
    path('user/<path:path>', views.UserManagementProxyView.as_view(), name='user_management_proxy'),
    path('book/<path:path>', views.BookApiProxyView.as_view(), name='book_api_proxy'),
    path('health/', views.health_check, name='health_check'),
]