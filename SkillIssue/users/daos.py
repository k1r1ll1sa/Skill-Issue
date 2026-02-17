from .models import Profile, GuideRating, Review, Guide, ProfileReview, Announcement, AnnouncementComment, ChatMessage
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, date
from .dto import GuideInfoDTO

class UserDAO:
    """DAO для профилей"""

    @staticmethod
    def get_all():
        return User.objects.all()

    @staticmethod
    def get_by_id(user_id):
        try:
            user = User.objects.get(id=user_id)
            return user
        except User.DoesNotExist:
            return None

    @staticmethod
    def get_username_by_id(user_id):
        try:
            user = User.objects.get(id=user_id)
            return user.username
        except User.DoesNotExist:
            return None

    @staticmethod
    def get_usernames_by_id_range(start, finish):
        users = User.objects.filter(
            id__gte=start,
            id__lte=finish
        ).order_by('id')
        return [user.username for user in users]

    @staticmethod
    def create_user(username, email, password, date_joined_str, is_active=True):
        try:
            date_joined = datetime.strptime(date_joined_str, "%Y-%m-%d %H:%M:%S")
            date_joined = timezone.make_aware(date_joined)
        except ValueError:
            date_joined = timezone.now()

        user = User.objects.create(
            username=username,
            email=email,
            password=password,
            date_joined=date_joined,
            is_active=is_active
        )
        return user

class ProfileDAO:
    """DAO для профилей"""

    @staticmethod
    def get_all():
        return Profile.objects.all()

    @staticmethod
    def get_by_user(user):
        try:
            return Profile.objects.get(user=user)
        except Profile.DoesNotExist:
            return None

class GuideDAO:
    """DAO для руководств"""

    @staticmethod
    def get_all():
        return Guide.objects.all()

    @staticmethod
    def search(guides=None, title=None, author=None, tag=None, min_rating=None):
        if guides is None:
            guides = Guide.objects.all()

        if title:
            guides = guides.filter(title__icontains=title)

        if author:
            guides = guides.filter(author=author)

        if tag:
            guides = guides.filter(tags__contains=[tag])

        if min_rating:
            guides = guides.filter(rating__gte=min_rating)

        return guides

    @staticmethod
    def get_by_id(guide_id):
        try:
            return Guide.objects.get(id=guide_id)
        except Guide.DoesNotExist:
            return None

    @staticmethod
    def create(title, content, author, tags=None, image=None):
        if tags is None:
            tags = []

        guide = Guide.objects.create(
            title=title,
            content=content,
            author=author,
            tags=tags,
            image=image
        )
        return guide

    @staticmethod
    def update(guide, **kwargs):
        for key, value in kwargs.items():
            if hasattr(guide, key):
                setattr(guide, key, value)
        guide.save()
        return guide

    @staticmethod
    def delete(guide):
        guide.delete()

    @staticmethod
    def get_guides_dto():
        rows = Guide.objects.select_related("author").values(
            "id", "title", "author__username", "rating"
        )

        return [
            GuideInfoDTO(
                id=r["id"],
                title=r["title"],
                author_username=r["author__username"],
                rating=r["rating"]
            )
            for r in rows
        ]

class AnnouncementDAO:
    """DAO для объявлений"""

    @staticmethod
    def get_all():
        return Announcement.objects.all()

    @staticmethod
    def get_by_id(announcement_id):
        try:
            announcement = Announcement.objects.get(id=announcement_id)
            return announcement
        except Announcement.DoesNotExist:
            return None

    @staticmethod
    def get_by_tag(tag):
        return Announcement.objects.filter(tags__contains=[tag])

class GuideRatingDAO:
    """DAO для рейтинга руководств"""

    @staticmethod
    def get_all():
        return GuideRating.objects.all()

class ReviewDAO:
    """DAO для комментария"""

    @staticmethod
    def get_all():
        return Review.objects.all()

class ProfileReviewDAO:
    """DAO для комментариев к профилям"""

    @staticmethod
    def get_all():
        return ProfileReview.objects.all()

class AnnouncementCommentDAO:
    """DAO для комментариев к объявлениям"""

    @staticmethod
    def get_all():
        return AnnouncementComment.objects.all()

    @staticmethod
    def create(announcement, author, content, created_at=None, updated_at=None, is_edited=None):

        announcement_comment = AnnouncementComment.objects.create(
            announcement=announcement,
            author=author,
            content=content,
            created_at=created_at,
            updated_at=updated_at,
            is_edited=is_edited
        )
        return announcement_comment

class ChatMessageDAO:
    """DAO для сообщения в чате"""

    @staticmethod
    def get_all():
        return ChatMessage.objects.all()

def test_index(user_id=1):
    target_date = date(2025, 1, 1)

    result = (AnnouncementComment.objects.filter(
        author_id=user_id,
        created_at__date__gte=target_date,
    ).exclude(
        announcement__author_id=user_id)
    .select_related(
        'announcement',
        'announcement__author'
        'author'
    ).values(
        'id',
        'announcement__title',
        'announcement__author__username',
        'author__username',
        'content',
        'created_at'
    ))

    return result

