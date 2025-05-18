from rest_framework import generics,status
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from accounts.serializers import UserSerializer, UserUpdateSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
class UserUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        user = request.user
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Данные пользователя обновлены", "data": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
# Вьюха для запроса сброса пароля
class PasswordResetRequestView(APIView):
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            user = User.objects.get(email=email)

            # Генерация токена и UID
            token_generator = PasswordResetTokenGenerator()
            token = token_generator.make_token(user)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

            # Формирование ссылки для сброса пароля
            reset_url = f"http://localhost:3000/reset-password/{uidb64}/{token}/"  # Для фронтенда

            # Отправка email
            subject = "Сброс пароля для Gnezdo"
            message = f"Привет, {user.username}!\n\nПерейди по ссылке, чтобы сбросить пароль:\n{reset_url}\n\nЕсли ты не запрашивал сброс, проигнорируй это письмо."
            send_mail(subject, message, 'your-email@gmail.com', [email], fail_silently=False)

            return Response({"message": "Письмо для сброса пароля отправлено"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Вьюха для подтверждения сброса пароля
class PasswordResetConfirmView(APIView):
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            uidb64 = serializer.validated_data['uidb64']
            token = serializer.validated_data['token']
            new_password = serializer.validated_data['new_password']

            try:
                user_id = force_str(urlsafe_base64_decode(uidb64))
                user = User.objects.get(pk=user_id)
            except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                return Response({"error": "Неверная ссылка"}, status=status.HTTP_400_BAD_REQUEST)

            token_generator = PasswordResetTokenGenerator()
            if token_generator.check_token(user, token):
                user.set_password(new_password)
                user.save()
                return Response({"message": "Пароль успешно сброшен"}, status=status.HTTP_200_OK)
            return Response({"error": "Неверный токен"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class UserDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user
        if not user.is_superuser and user != request.user:
            return Response({"error": "Вы не можете удалить другого пользователя."}, status=status.HTTP_403_FORBIDDEN)
        user.delete()
        return Response({"message": "Пользователь успешно удален"}, status=status.HTTP_200_OK)