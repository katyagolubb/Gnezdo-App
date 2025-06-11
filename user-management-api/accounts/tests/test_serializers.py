from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError
from .serializers import (
    UserSerializer,
    UserUpdateSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer
)

User = get_user_model()


class UserSerializerTest(TestCase):
    def setUp(self):
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User',
            'phone': '+1234567890'
        }

    def test_create_user(self):
        """Тест создания пользователя через сериализатор"""
        serializer = UserSerializer(data=self.user_data)
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('testpass123'))
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        self.assertEqual(user.phone, '+1234567890')

    def test_password_write_only(self):
        """Тест что пароль не возвращается в ответе"""
        serializer = UserSerializer(data=self.user_data)
        serializer.is_valid()
        data = serializer.data
        
        self.assertNotIn('password', data)

    def test_required_fields(self):
        """Тест обязательных полей"""
        incomplete_data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        serializer = UserSerializer(data=incomplete_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)


class UserUpdateSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='existinguser',
            email='existing@example.com',
            password='testpass123'
        )
        self.update_data = {
            'username': 'updateduser',
            'email': 'updated@example.com',
            'first_name': 'Updated',
            'last_name': 'User',
            'phone': '+987654321'
        }

    def test_partial_update(self):
        """Тест частичного обновления"""
        serializer = UserUpdateSerializer(
            instance=self.user,
            data={'first_name': 'Partial'},
            partial=True
        )
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        
        self.assertEqual(user.first_name, 'Partial')
        self.assertEqual(user.username, 'existinguser')  # Другие поля не изменились

    def test_full_update(self):
        """Тест полного обновления"""
        serializer = UserUpdateSerializer(
            instance=self.user,
            data=self.update_data
        )
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        
        self.assertEqual(user.username, 'updateduser')
        self.assertEqual(user.email, 'updated@example.com')
        self.assertEqual(user.first_name, 'Updated')

    def test_email_uniqueness_validation(self):
        """Тест валидации уникальности email"""
        User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        serializer = UserUpdateSerializer(
            instance=self.user,
            data={'email': 'other@example.com'}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

    def test_username_uniqueness_validation(self):
        """Тест валидации уникальности username"""
        User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        serializer = UserUpdateSerializer(
            instance=self.user,
            data={'username': 'otheruser'}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('username', serializer.errors)


class PasswordResetRequestSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_valid_email(self):
        """Тест с существующим email"""
        serializer = PasswordResetRequestSerializer(data={'email': 'test@example.com'})
        self.assertTrue(serializer.is_valid())

    def test_invalid_email(self):
        """Тест с несуществующим email"""
        serializer = PasswordResetRequestSerializer(data={'email': 'nonexistent@example.com'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)


class PasswordResetConfirmSerializerTest(TestCase):
    def test_required_fields(self):
        """Тест обязательных полей"""
        serializer = PasswordResetConfirmSerializer(data={
            'new_password': 'newpass123',
            'uidb64': 'testuid',
            'token': 'testtoken'
        })
        self.assertTrue(serializer.is_valid())

    def test_missing_fields(self):
        """Тест отсутствия обязательных полей"""
        incomplete_data = {'new_password': 'newpass123'}
        serializer = PasswordResetConfirmSerializer(data=incomplete_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('uidb64', serializer.errors)
        self.assertIn('token', serializer.errors)