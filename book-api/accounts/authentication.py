from django.contrib.auth import get_user_model
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings


class AutoProvisionJWTAuthentication(JWTAuthentication):
    """
    Book API хранит свои доменные данные, но аутентификация идёт JWT из user-management-api.
    Если пользователь с user_id из токена ещё не создан локально — создаём минимальную запись.
    """

    def get_user(self, validated_token):
        User = get_user_model()

        user_id = validated_token.get(api_settings.USER_ID_CLAIM)
        if user_id is None:
            raise exceptions.AuthenticationFailed(
                "Token contained no recognizable user identification",
                code="user_not_found",
            )

        try:
            return User.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        except User.DoesNotExist:
            # Минимальный user, чтобы работали связи/permissions в Book API
            username = f"user_{user_id}"
            email = f"user_{user_id}@example.com"
            user = User(**{api_settings.USER_ID_FIELD: user_id, "username": username, "email": email})
            user.set_unusable_password()
            user.save(force_insert=True)
            return user

