from django.test import TestCase
from django.contrib.auth import get_user_model
from cloudinary.models import CloudinaryField

User = get_user_model()


class UserModelTest(TestCase):
    def setUp(self):
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User',
            'phone': '+1234567890'
        }
        self.user = User.objects.create_user(**self.user_data)

    def test_user_creation(self):
        """Тест создания пользователя"""
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.first()
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('testpass123'))

    def test_email_uniqueness(self):
        """Тест уникальности email"""
        with self.assertRaises(Exception):
            User.objects.create_user(
                username='anotheruser',
                email='test@example.com',
                password='testpass123'
            )

    def test_user_fields(self):
        """Тест полей пользователя"""
        user = self.user
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        self.assertEqual(user.phone, '+1234567890')
        self.assertIsNotNone(user.created_at)

    def test_photo_field(self):
        """Тест поля photo"""
        field = User._meta.get_field('photo')
        self.assertIsInstance(field, CloudinaryField)
        # Проверяем, что поле допускает пустые значения
        self.assertTrue(field.blank)
        self.assertTrue(field.null)

    def test_str_representation(self):
        """Тест строкового представления"""
        self.assertEqual(str(self.user), 'testuser')

    def test_optional_fields(self):
        """Тест необязательных полей"""
        user = User.objects.create_user(
            username='minimaluser',
            email='minimal@example.com',
            password='testpass123'
        )
        self.assertIsNone(user.photo)
        self.assertEqual(user.first_name, '')
        self.assertEqual(user.last_name, '')
        self.assertIsNone(user.phone)