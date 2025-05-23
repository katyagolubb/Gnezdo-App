# books/serializers.py
from rest_framework import serializers
from books.models import Book, UserBook, Photo, ExchangeRequest
from accounts.models import User

class BookSuggestionSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    author = serializers.CharField()
    overview = serializers.CharField()
    genres = serializers.CharField()

class BookCreateSerializer(serializers.ModelSerializer):
    genres = serializers.CharField(max_length=255, allow_blank=True, required=False)

    class Meta:
        model = Book
        fields = ['book_id', 'name', 'author', 'overview', 'genres']

    def validate_genres(self, value):
        if value and len(value) > 255:
            raise serializers.ValidationError("Ensure this field has no more than 255 characters.")
        return value

    def to_internal_value(self, data):
        if 'genres' in data and isinstance(data['genres'], str):
            genres = data['genres'].split(', ')
            data['genres'] = self.normalize_genres(genres)
        elif 'genres' in data and isinstance(data['genres'], list):
            data['genres'] = self.normalize_genres(data['genres'])
        return super().to_internal_value(data)

    def normalize_genres(self, genres_list):
        normalized = []
        seen = set()
        for genre in genres_list:
            if isinstance(genre, str):
                parts = [part.strip() for part in genre.split('/') if part.strip()]
                for part in parts:
                    if part and part not in seen:
                        seen.add(part)
                        normalized.append(part)
        return ', '.join(normalized) if normalized else ''

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Возвращаем жанры как список
        genres = instance.genres.values_list('name', flat=True)
        representation['genres'] = list(genres) if genres else ['Unknown']
        return representation

class UserBookCreateSerializer(serializers.ModelSerializer):
    book_id = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all())
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = UserBook
        fields = ['user_book_id', 'user', 'book_id', 'condition', 'location']

    def validate_user(self, value):
        if not value.id:
            raise serializers.ValidationError("Invalid user")
        return value

    def validate_condition(self, value):
        if not value or not isinstance(value, str):
            raise serializers.ValidationError("Condition is required and must be a string")
        return value

    def validate_location(self, value):
        if not value or not isinstance(value, str):
            raise serializers.ValidationError("Location is required and must be a string")
        if value:
            try:
                lat, lon = map(float, value.split(','))
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError
                return value
            except (ValueError, AttributeError):
                raise serializers.ValidationError("Location must be 'lat,lon' (e.g., '55.7558,37.6173')")
        return value

    def create(self, validated_data):
        user = validated_data.pop('user')
        book_id = validated_data.pop('book_id')
        return UserBook.objects.create(user=user, book_id=book_id, **validated_data)

class UserBookSerializer(serializers.ModelSerializer):
    book = BookCreateSerializer(source='book_id', read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = UserBook
        fields = ['user_book_id', 'book', 'condition', 'location', 'status']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if 'book' in representation and 'genres' in representation['book']:
            genres = representation['book']['genres']
            if not genres or genres == ['Unknown']:
                representation['book']['genres'] = ['Unknown']
            # Уже список, оставляем как есть
        return representation

class PhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Photo
        fields = ['photo_id', 'user_book_id', 'file_path']

    def validate(self, data):
        user_book = data.get('user_book_id')
        if not user_book:
            raise serializers.ValidationError("user_book_id is required.")

        request = self.context.get('request')
        if request and not request.user.is_superuser and user_book.user != request.user:
            raise serializers.ValidationError("You do not have permission to upload photos for this book.")

        return data

    def validate_file_path(self, value):
        if not value.startswith('https://res.cloudinary.com'):
            raise serializers.ValidationError("Invalid file path. Must be a valid Cloudinary URL.")
        return value

class PhotoUploadSerializer(serializers.Serializer):
    user_book_id = serializers.PrimaryKeyRelatedField(queryset=UserBook.objects.all())
    file = serializers.FileField()

    def validate_file(self, value):
        max_size = 5 * 1024 * 1024  # 5MB
        if value.size > max_size:
            raise serializers.ValidationError("File size must be less than 5MB.")

        allowed_formats = ['image/jpeg', 'image/png', 'image/gif']
        if value.content_type not in allowed_formats:
            raise serializers.ValidationError("File must be an image (JPEG, PNG, or GIF).")

        return value

    def validate(self, data):
        user_book = data.get('user_book_id')
        request = self.context.get('request')
        if request and not request.user.is_superuser and user_book.user != request.user:
            raise serializers.ValidationError("You do not have permission to upload photos for this book.")

        return data

class ExchangeRequestSerializer(serializers.ModelSerializer):
    book = UserBookSerializer(read_only=True)
    requester = serializers.StringRelatedField(read_only=True)
    owner = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = ExchangeRequest
        fields = ['exchange_request_id', 'book', 'requester', 'owner', 'status', 'created_at']