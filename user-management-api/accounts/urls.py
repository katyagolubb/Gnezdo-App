from django.urls import path
from .views import RegisterView, UserUpdateView, PasswordResetRequestView, PasswordResetConfirmView, UserDeleteView, UserDetailView, OtherUserDetailView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('update/', UserUpdateView.as_view(), name='user-update'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('delete/', UserDeleteView.as_view(), name='user-delete'),
    path('me/', UserDetailView.as_view(), name='user-detail'),
    path('users/<int:pk>/', OtherUserDetailView.as_view(), name='other-user-detail'),  # Новый маршрут
]