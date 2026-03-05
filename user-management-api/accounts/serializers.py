from rest_framework import serializers
from .models import User
import re


USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9._-]+$")
NAME_REGEX = re.compile(r"^[A-Za-zА-Яа-яЁё' -]+$")


def validate_password_strength(value: str) -> str:
    """
    Общий валидатор пароля для регистрации и сброса пароля.
    Требования (F_Auth_1):
    - длина от 8 до 128 символов
    - минимум одна буква и одна цифра
    """
    if not (8 <= len(value) <= 128):
        raise serializers.ValidationError("Пароль должен быть длиной от 8 до 128 символов.")
    if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
        raise serializers.ValidationError("Пароль должен содержать как минимум одну букву и одну цифру.")
    return value

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'first_name', 'last_name', 'phone', 'photo']
        extra_kwargs = {
            # Уникальность/формат проверяем в validate_* с русскими сообщениями,
            # поэтому отключаем дефолтные validators ModelSerializer.
            "username": {"validators": []},
            "email": {"validators": []},
        }

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone=validated_data.get('phone', ''),
            photo=validated_data.get('photo', None)
        )
        return user

    # --- Валидации по требованиям F_Auth_1 ---

    def validate_username(self, value: str) -> str:
        # Длина 3–30, только [a-zA-Z0-9._-], без пробелов, уникальность
        if not (3 <= len(value) <= 30):
            raise serializers.ValidationError("Имя пользователя должно быть длиной от 3 до 30 символов.")
        if not USERNAME_REGEX.match(value):
            raise serializers.ValidationError(
                "Имя пользователя может содержать только латинские буквы, цифры и символы . _ - без пробелов."
            )
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Пользователь с таким именем уже существует.")
        return value

    def validate_email(self, value: str) -> str:
        # Длина ≤ 254, формат проверяется EmailField, уникальность без учета регистра
        if len(value) > 254:
            raise serializers.ValidationError("Email не может быть длиной более 254 символов.")
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует.")
        # Нормализуем email к нижнему регистру для единообразия
        return value.lower()

    def validate_password(self, value: str) -> str:
        return validate_password_strength(value)

    def validate_first_name(self, value: str) -> str:
        # Необязательное поле, но если задано — только буквы/пробел/дефис/апостроф
        if value and not NAME_REGEX.match(value):
            raise serializers.ValidationError(
                "Имя может содержать только буквы, пробелы, дефисы и апострофы."
            )
        return value

    def validate_last_name(self, value: str) -> str:
        if value and not NAME_REGEX.match(value):
            raise serializers.ValidationError(
                "Фамилия может содержать только буквы, пробелы, дефисы и апострофы."
            )
        return value

    def validate_phone(self, value: str) -> str:
        # Необязательное поле; если заполнено — формат +7XXXXXXXXXX, уникальность
        if not value:
            return value
        if not re.match(r"^\+7\d{10}$", value):
            raise serializers.ValidationError(
                "Телефон должен быть в формате +7XXXXXXXXXX и содержать только цифры."
            )
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Пользователь с таким номером телефона уже существует.")
        return value

    def validate_photo(self, value):
        # Необязательное поле; допустимые расширения и размер ≤ 5 МБ (если файл загружается через API)
        if not value:
            return value
        # SimpleUploadedFile хранит content_type на самом объекте,
        # а CloudinaryFile может проксировать его через .file
        file_obj = getattr(value, "file", None) or value
        content_type = getattr(value, "content_type", None) or getattr(file_obj, "content_type", None)
        size = getattr(value, "size", None) or getattr(file_obj, "size", None)

        if content_type not in ("image/jpeg", "image/png"):
            raise serializers.ValidationError("Допустимы только изображения JPEG или PNG.")
        max_size = 5 * 1024 * 1024  # 5 МБ
        if size is not None and size > max_size:
            raise serializers.ValidationError("Размер файла не должен превышать 5 МБ.")
        return value


class PublicUserSerializer(serializers.ModelSerializer):
    """
    Публичный профиль пользователя (F_User_2).
    Доступен всем аутентифицированным пользователям.
    """

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'photo']


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'photo']
        extra_kwargs = {
            'email': {'required': False},
            'username': {'required': False},
            'first_name': {'required': False},
            'last_name': {'required': False},
            'phone': {'required': False},
            'photo': {'required': False},
        }

    def validate_email(self, value: str) -> str:
        if len(value) > 254:
            raise serializers.ValidationError("Email не может быть длиной более 254 символов.")
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=value).exists():
            raise serializers.ValidationError("Этот email уже используется.")
        return value.lower()

    def validate_username(self, value: str) -> str:
        if not (3 <= len(value) <= 30):
            raise serializers.ValidationError("Имя пользователя должно быть длиной от 3 до 30 символов.")
        if not USERNAME_REGEX.match(value):
            raise serializers.ValidationError(
                "Имя пользователя может содержать только латинские буквы, цифры и символы . _ - без пробелов."
            )
        if User.objects.exclude(pk=self.instance.pk).filter(username=value).exists():
            raise serializers.ValidationError("Это имя пользователя уже занято.")
        return value

    def validate_first_name(self, value: str) -> str:
        if value and not NAME_REGEX.match(value):
            raise serializers.ValidationError(
                "Имя может содержать только буквы, пробелы, дефисы и апострофы."
            )
        return value

    def validate_last_name(self, value: str) -> str:
        if value and not NAME_REGEX.match(value):
            raise serializers.ValidationError(
                "Фамилия может содержать только буквы, пробелы, дефисы и апострофы."
            )
        return value

    def validate_phone(self, value: str) -> str:
        if not value:
            return value
        if not re.match(r"^\+7\d{10}$", value):
            raise serializers.ValidationError(
                "Телефон должен быть в формате +7XXXXXXXXXX и содержать только цифры."
            )
        if User.objects.exclude(pk=self.instance.pk).filter(phone=value).exists():
            raise serializers.ValidationError("Пользователь с таким номером телефона уже существует.")
        return value

    def validate_photo(self, value):
        if not value:
            return value
        file_obj = getattr(value, "file", None) or value
        content_type = getattr(file_obj, "content_type", None)
        size = getattr(file_obj, "size", None)

        if content_type not in ("image/jpeg", "image/png"):
            raise serializers.ValidationError("Допустимы только изображения JPEG или PNG.")
        max_size = 5 * 1024 * 1024
        if size is not None and size > max_size:
            raise serializers.ValidationError("Размер файла не должен превышать 5 МБ.")
        return value


# Сериализатор для запроса сброса пароля
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        # Поиск без учета регистра (F_Auth_1)
        if not User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Пользователь с таким email не найден.")
        return value.lower()

# Сериализатор для подтверждения сброса пароля
class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    uidb64 = serializers.CharField()
    token = serializers.CharField()

    def validate_new_password(self, value: str) -> str:
        # Повторяем требования к паролю из регистрации (F_Auth_4 -> F_Auth_1)
        return validate_password_strength(value)