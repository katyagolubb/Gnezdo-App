# books/serializers.py
from rest_framework import serializers
from books.models import Book, UserBook, Photo
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
                parts = genre.split('/')
                if parts:
                    last_part = parts[-1].strip()
                    if last_part and last_part not in seen:
                        seen.add(last_part)
                        normalized.append(last_part)
        return ', '.join(normalized) if normalized else ''

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

    class Meta:
        model = UserBook
        fields = ['user_book_id', 'book', 'condition', 'location']