from django.test import TestCase
from rest_framework.test import APITestCase, APIRequestFactory, force_authenticate
from rest_framework import status
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from accounts.views import (
    RegisterView,
    UserUpdateView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    UserDeleteView,
    UserDetailView,
    OtherUserDetailView,
)
from accounts.serializers import UserSerializer

User = get_user_model()


class RegisterViewTest(APITestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RegisterView.as_view()
        self.url = '/api/register/'
        self.valid_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123',
        }

    def test_register_user_success(self):
        request = self.factory.post(self.url, self.valid_data, format='json')
        response = self.view(request)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.get().username, 'testuser')

    def test_register_user_invalid_data(self):
        invalid_data = self.valid_data.copy()
        invalid_data['email'] = 'invalid-email'
        request = self.factory.post(self.url, invalid_data, format='json')
        response = self.view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 0)


class UserUpdateViewTest(APITestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = UserUpdateView.as_view()
        self.url = '/api/user/update/'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.valid_data = {
            'username': 'updateduser',
            'email': 'updated@example.com',
        }

    def test_update_user_success(self):
        request = self.factory.put(self.url, self.valid_data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'updateduser')
        self.assertEqual(self.user.email, 'updated@example.com')

    def test_update_user_unauthenticated(self):
        request = self.factory.put(self.url, self.valid_data, format='json')
        response = self.view(request)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PasswordResetTest(APITestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.request_view = PasswordResetRequestView.as_view()
        self.confirm_view = PasswordResetConfirmView.as_view()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='oldpassword'
        )
        self.reset_request_url = '/api/password/reset/'
        self.reset_confirm_url = '/api/password/reset/confirm/'
        
        # Generate token and uid for confirm tests
        self.token_generator = PasswordResetTokenGenerator()
        self.token = self.token_generator.make_token(self.user)
        self.uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))

    def test_password_reset_request_success(self):
        request = self.factory.post(self.reset_request_url, {'email': 'test@example.com'}, format='json')
        response = self.request_view(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Письмо для сброса пароля отправлено', response.data['message'])

    def test_password_reset_request_invalid_email(self):
        request = self.factory.post(self.reset_request_url, {'email': 'wrong@example.com'}, format='json')
        response = self.request_view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_confirm_success(self):
        data = {
            'uidb64': self.uidb64,
            'token': self.token,
            'new_password': 'newpassword123',
        }
        request = self.factory.post(self.reset_confirm_url, data, format='json')
        response = self.confirm_view(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpassword123'))

    def test_password_reset_confirm_invalid_token(self):
        data = {
            'uidb64': self.uidb64,
            'token': 'invalid-token',
            'new_password': 'newpassword123',
        }
        request = self.factory.post(self.reset_confirm_url, data, format='json')
        response = self.confirm_view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


class UserDeleteViewTest(APITestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = UserDeleteView.as_view()
        self.url = '/api/user/delete/'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )

    def test_delete_user_success(self):
        request = self.factory.delete(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.count(), 1)  # only other_user remains

    def test_delete_user_unauthenticated(self):
        request = self.factory.delete(self.url)
        response = self.view(request)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class UserDetailViewTest(APITestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = UserDetailView.as_view()
        self.url = '/api/user/'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_get_user_detail(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertEqual(response.data['email'], 'test@example.com')


class OtherUserDetailViewTest(APITestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OtherUserDetailView.as_view()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )

    def test_get_other_user_detail(self):
        url = f'/api/users/{self.other_user.id}/'
        request = self.factory.get(url)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=self.other_user.id)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'otheruser')
        self.assertEqual(response.data['email'], 'other@example.com')

    def test_get_nonexistent_user(self):
        url = '/api/users/999/'
        request = self.factory.get(url)
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=999)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)