from django.test import TestCase, Client
from django.urls import reverse, resolve
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase
from rest_framework import status

from accounts.views import (
    RegisterView,
    UserUpdateView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    UserDeleteView,
    UserDetailView,
    OtherUserDetailView,
)

User = get_user_model()


class URLTests(TestCase):
    def test_urls_resolve_correct_views(self):
        """Тест что URL разрешаются в правильные представления"""
        url_view_mapping = {
            'register': RegisterView,
            'user-update': UserUpdateView,
            'password-reset-request': PasswordResetRequestView,
            'password-reset-confirm': PasswordResetConfirmView,
            'user-delete': UserDeleteView,
            'user-detail': UserDetailView,
            'other-user-detail': OtherUserDetailView,
        }
        
        for url_name, view_class in url_view_mapping.items():
            if url_name == 'other-user-detail':
                url = reverse(url_name, kwargs={'pk': 1})
            else:
                url = reverse(url_name)
            
            self.assertEqual(resolve(url).func.view_class, view_class)


class UserViewsTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )

    def test_register_view(self):
        """Тест регистрации пользователя"""
        url = reverse('register')
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'newpass123',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_user_detail_view_authenticated(self):
        """Тест получения информации о текущем пользователе (аутентифицированный)"""
        self.client.force_authenticate(user=self.user)
        url = reverse('user-detail')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')

    def test_user_detail_view_unauthenticated(self):
        """Тест получения информации о текущем пользователе (неаутентифицированный)"""
        url = reverse('user-detail')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_user_detail_view(self):
        """Тест получения информации о другом пользователе"""
        url = reverse('other-user-detail', kwargs={'pk': self.other_user.pk})
        # Доступ только для аутентифицированных пользователей (F_User_2)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'otheruser')
        self.assertNotIn('email', response.data)  # Проверяем что email не возвращается

    def test_user_update_view(self):
        """Тест обновления информации пользователя"""
        self.client.force_authenticate(user=self.user)
        url = reverse('user-update')
        data = {
            'first_name': 'Updated',
            'last_name': 'Name'
        }
        
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')

    def test_password_reset_request_view(self):
        """Тест запроса сброса пароля"""
        url = reverse('password-reset-request')
        data = {'email': 'test@example.com'}
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_confirm_view(self):
        """Тест подтверждения сброса пароля"""
        url = reverse('password-reset-confirm')
        data = {
            'new_password': 'newpass123',
            'uidb64': 'testuid',
            'token': 'testtoken'
        }
        
        response = self.client.post(url, data, format='json')
        # Здесь должен быть более сложный тест с реальным uid и токеном
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_user_delete_view(self):
        """Тест удаления пользователя"""
        self.client.force_authenticate(user=self.user)
        url = reverse('user-delete')
        
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())


class AuthenticationTests(APITestCase):
    def test_access_to_protected_views(self):
        """Тест доступа к защищенным представлениям"""
        protected_urls = [
            reverse('user-update'),
            reverse('user-delete'),
            reverse('user-detail'),
        ]
        
        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)