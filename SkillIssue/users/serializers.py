from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Profile, Review, Guide, Announcement, ChatMessage, ProfileReview


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ("username", "email", "password")

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"]
        )
        Profile.objects.create(user=user)
        return user


class ReviewSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    author_avatar = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ['id', 'author_username', 'author_avatar', 'text', 'stars', 'created_at']

    def get_author_avatar(self, obj):
        if hasattr(obj.author, 'profile') and obj.author.profile.avatar:
            return obj.author.profile.avatar.url
        return None


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    rating = serializers.FloatField(read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    guides = serializers.SerializerMethodField()
    announcements = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ["username", "avatar", "bio", "rating", "reviews", "guides", "announcements"]

    def get_guides(self, obj):
        guides = Guide.objects.filter(author=obj.user).order_by('-created_at')
        return GuideSerializer(guides, many=True).data

    def get_announcements(self, obj):
        announcements = Announcement.objects.filter(author=obj.user).order_by('-created_at')
        return AnnouncementSerializer(announcements, many=True).data


class GuideSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = Guide
        fields = ['id', 'title', 'content', 'image', 'tags', 'rating', 'author_name', 'created_at']


class AnnouncementSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = Announcement
        fields = ['id', 'title', 'description', 'image', 'author', 'tags', 'created_at', 'updated_at']


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    receiver_username = serializers.CharField(source="receiver.username", read_only=True)
    direction = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "sender",
            "receiver",
            "sender_username",
            "receiver_username",
            "message",
            "image",
            "image_url",
            "created_at",
            "is_read",
            "direction",
        ]
        read_only_fields = ["id", "sender", "receiver", "created_at", "is_read", "direction", "image_url"]

    def get_direction(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            return "outgoing" if obj.sender_id == request.user.id else "incoming"
        return "incoming"

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

    def validate(self, data):
        # Проверка: должно быть хотя бы одно из полей
        if not data.get('message') and not self.context.get('request').FILES.get('image'):
            raise serializers.ValidationError({
                'error': 'Сообщение должно содержать текст или изображение'
            })
        return data


class ChatContactSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    avatar = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    last_message = serializers.CharField(allow_blank=True)
    last_message_at = serializers.DateTimeField(allow_null=True)
    unread_count = serializers.IntegerField()


class ProfileCommentSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source='reviewer.username', read_only=True)
    author_avatar = serializers.SerializerMethodField()
    profile = serializers.CharField(source='profile.user.username', read_only=True)
    created_at = serializers.DateTimeField(format='%d.%m.%Y %H:%M', read_only=True)
    is_edited = serializers.BooleanField(read_only=True)

    class Meta:
        model = ProfileReview
        fields = ['id', 'comment', 'author', 'author_avatar', 'profile', 'created_at', 'is_edited']

    def get_author_avatar(self, obj):
        if hasattr(obj.reviewer, 'profile') and obj.reviewer.profile.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.reviewer.profile.avatar.url)
            return obj.reviewer.profile.avatar.url
        return None
