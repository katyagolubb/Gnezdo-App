from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError
from accounts.serializers import (
    UserSerializer,
    UserUpdateSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
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
            'phone': '+79991234567',
        }

    def test_create_user(self):
        """Тест создания пользователя через сериализатор"""
        serializer = UserSerializer(data=self.user_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()

        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('testpass123'))
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        self.assertEqual(user.phone, '+79991234567')

    def test_password_write_only(self):
        """Тест что пароль не возвращается в ответе"""
        serializer = UserSerializer(data=self.user_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        # Представление данных существующего пользователя
        data = UserSerializer(instance=user).data
        self.assertNotIn('password', data)

    def test_required_fields(self):
        """Тест обязательных полей"""
        incomplete_data = {
            'username': 'testuser',
            'password': 'testpass123',
        }
        serializer = UserSerializer(data=incomplete_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

    # --- Валидация имени пользователя (F_Auth_1) ---

    def test_username_too_short(self):
        data = self.user_data.copy()
        data['username'] = 'ab'
        serializer = UserSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('username', serializer.errors)

    def test_username_too_long(self):
        data = self.user_data.copy()
        data['username'] = 'a' * 31
        serializer = UserSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('username', serializer.errors)

    def test_username_invalid_characters(self):
        data = self.user_data.copy()
        data['username'] = 'bad user!'
        serializer = UserSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('username', serializer.errors)

    def test_username_valid_mask(self):
        data = self.user_data.copy()
        data['username'] = 'valid.user-name_123'
        serializer = UserSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    # --- Email (длина, регистронезависимая уникальность) ---

    def test_email_too_long(self):
        # Делаем email длиной > 254 символов
        local_part = 'a' * 248
        data = self.user_data.copy()
        data['email'] = f'{local_part}@ex.com'
        serializer = UserSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

    def test_email_case_insensitive_uniqueness(self):
        User.objects.create_user(
            username='existing',
            email='Test@Example.com',
            password='testpass123',
        )
        data = self.user_data.copy()
        data['email'] = 'test@example.com'
        serializer = UserSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

    # --- Пароль (F_Auth_1, F_Auth_4) ---

    def test_password_too_short(self):
        data = self.user_data.copy()
        data['password'] = 'a1b2c3'
        serializer = UserSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_password_without_digit(self):
        data = self.user_data.copy()
        data['password'] = 'abcdefgh'
        serializer = UserSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_password_without_letter(self):
        data = self.user_data.copy()
        data['password'] = '12345678'
        serializer = UserSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    # --- Имя / фамилия ---

    def test_first_name_invalid_characters(self):
        data = self.user_data.copy()
        data['first_name'] = 'Test123'
        serializer = UserSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('first_name', serializer.errors)

    def test_last_name_invalid_characters(self):
        data = self.user_data.copy()
        data['last_name'] = 'User!'
        serializer = UserSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('last_name', serializer.errors)

    # --- Телефон ---

    def test_phone_invalid_format(self):
        data = self.user_data.copy()
        data['phone'] = '+1234567890'
        serializer = UserSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('phone', serializer.errors)

    def test_phone_uniqueness(self):
        User.objects.create_user(
            username='other',
            email='other@example.com',
            password='testpass123',
            phone='+79991234567',
        )
        data = self.user_data.copy()
        data['phone'] = '+79991234567'
        serializer = UserSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('phone', serializer.errors)

    # --- Фото ---

    def test_photo_invalid_content_type(self):
        file_obj = SimpleUploadedFile(
            'avatar.gif',
            b'fakegif',
            content_type='image/gif',
        )
        data = self.user_data.copy()
        data['photo'] = file_obj
        serializer = UserSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('photo', serializer.errors)

    def test_photo_too_large(self):
        # > 5 МБ
        big_content = b'a' * (5 * 1024 * 1024 + 1)
        file_obj = SimpleUploadedFile(
            'avatar.png',
            big_content,
            content_type='image/png',
        )
        data = self.user_data.copy()
        data['photo'] = file_obj
        serializer = UserSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('photo', serializer.errors)

    def test_photo_valid_png(self):
        file_obj = SimpleUploadedFile(
            'avatar.png',
            b'\x89PNG\r\n\x1a\n',
            content_type='image/png',
        )
        data = self.user_data.copy()
        data['photo'] = file_obj
        serializer = UserSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)


class UserUpdateSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='existinguser',
            email='existing@example.com',
            password='testpass123',
            phone='+79990000000',
        )
        self.update_data = {
            'username': 'updateduser',
            'email': 'updated@example.com',
            'first_name': 'Updated',
            'last_name': 'User',
            'phone': '+79991234567',
        }

    def test_partial_update(self):
        """Тест частичного обновления"""
        serializer = UserUpdateSerializer(
            instance=self.user,
            data={'first_name': 'Partial'},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()

        self.assertEqual(user.first_name, 'Partial')
        self.assertEqual(user.username, 'existinguser')  # Другие поля не изменились

    def test_full_update(self):
        """Тест полного обновления"""
        serializer = UserUpdateSerializer(
            instance=self.user,
            data=self.update_data,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()

        self.assertEqual(user.username, 'updateduser')
        self.assertEqual(user.email, 'updated@example.com')
        self.assertEqual(user.first_name, 'Updated')
        self.assertEqual(user.phone, '+79991234567')

    def test_email_uniqueness_validation(self):
        """Тест валидации уникальности email (без учета регистра)"""
        User.objects.create_user(
            username='otheruser',
            email='Other@Example.com',
            password='testpass123',
        )

        serializer = UserUpdateSerializer(
            instance=self.user,
            data={'email': 'other@example.com'},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

    def test_username_uniqueness_validation(self):
        """Тест валидации уникальности username"""
        User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123',
        )

        serializer = UserUpdateSerializer(
            instance=self.user,
            data={'username': 'otheruser'},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('username', serializer.errors)

    def test_update_username_invalid_format(self):
        serializer = UserUpdateSerializer(
            instance=self.user,
            data={'username': 'bad name'},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('username', serializer.errors)

    def test_update_phone_invalid_format(self):
        serializer = UserUpdateSerializer(
            instance=self.user,
            data={'phone': '+1234567890'},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('phone', serializer.errors)

    def test_update_phone_uniqueness(self):
        User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123',
            phone='+79995555555',
        )
        serializer = UserUpdateSerializer(
            instance=self.user,
            data={'phone': '+79995555555'},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('phone', serializer.errors)

    def test_update_first_name_invalid(self):
        serializer = UserUpdateSerializer(
            instance=self.user,
            data={'first_name': 'Name123'},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('first_name', serializer.errors)

    def test_update_last_name_invalid(self):
        serializer = UserUpdateSerializer(
            instance=self.user,
            data={'last_name': 'User!'},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('last_name', serializer.errors)


class PasswordResetRequestSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='Test@Example.com',
            password='testpass123',
        )

    def test_valid_email(self):
        """Тест с существующим email"""
        serializer = PasswordResetRequestSerializer(data={'email': 'test@example.com'})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_email(self):
        """Тест с несуществующим email"""
        serializer = PasswordResetRequestSerializer(data={'email': 'nonexistent@example.com'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)


class PasswordResetConfirmSerializerTest(TestCase):
    def test_required_fields(self):
        """Тест обязательных полей и требований к паролю"""
        serializer = PasswordResetConfirmSerializer(data={
            'new_password': 'newpass1234',
            'uidb64': 'testuid',
            'token': 'testtoken',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_missing_fields(self):
        """Тест отсутствия обязательных полей"""
        incomplete_data = {'new_password': 'newpass123'}
        serializer = PasswordResetConfirmSerializer(data=incomplete_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('uidb64', serializer.errors)
        self.assertIn('token', serializer.errors)

    def test_new_password_too_weak(self):
        """Пароль без цифр/букв не принимается"""
        serializer = PasswordResetConfirmSerializer(data={
            'new_password': 'short',
            'uidb64': 'testuid',
            'token': 'testtoken',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('new_password', serializer.errors)