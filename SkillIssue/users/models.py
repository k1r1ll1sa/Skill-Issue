from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User

ACTION_CHOICES = [
    ('CREATE', 'Создание'),
    ('UPDATE', 'Обновление'),
    ('DELETE', 'Удаление'),
]

TARGET_TYPE_CHOICES = [
    ('GUIDE', 'Руководство'),
    ('ANNOUNCEMENT', 'Объявление'),
]

class Profile(models.Model):
    """Модель профиля"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
    )

    def __str__(self):
        return self.user.username


class Announcement(models.Model):
    """Модель объявления"""
    title = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to='announcements/', blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='announcements')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tags = models.JSONField(default=list)

    def __str__(self):
        return self.title


class ChatMessage(models.Model):
    """Модель сообщения в чате"""
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Сообщение от {self.sender} к {self.receiver}"


class Guide(models.Model):
    """Модель руководства"""
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='guides')
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    image = models.ImageField(upload_to='guides/', blank=True, null=True)
    tags = models.JSONField(blank=True, default=list)
    rating = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class GuideComment(models.Model):
    """Модель комментария к профилю"""
    guide = models.ForeignKey(Guide, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)

    def __str__(self):
        return f"Комментарий от {self.author} к {self.guide}"


class AnnouncementComment(models.Model):
    """Модель комментария к объявлению"""
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='commented_announcements')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)

    def __str__(self):
        return f"Комментарий от {self.author} к объявлению {self.announcement}"


class Review(models.Model):
    """Модель комментария к руководству"""
    guide = models.ForeignKey(Guide, on_delete=models.CASCADE, related_name="reviews")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    stars = models.PositiveSmallIntegerField(default=5)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Review({self.author.username} → {self.guide.title})"


class GuideRating(models.Model):
    """Модель оценки руководства"""
    guide = models.ForeignKey(Guide, on_delete=models.CASCADE, related_name='ratings')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])  # 1–5 звёзд
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('guide', 'reviewer')

    def __str__(self):
        return f"{self.reviewer} оценил {self.guide} на {self.rating}"


class ProfileReview(models.Model):
    """Модель комментария к профилю"""
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_reviews')
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='reviews')
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('reviewer', 'profile')

    def __str__(self):
        return f"Отзыв от {self.reviewer} на {self.profile}"


class EmailVerificationCode(models.Model):
    """Модель для хранения кодов подтверждения email"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_codes')
    code = models.CharField(max_length=6)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Код для {self.email}: {self.code}"

    def is_expired(self):
        """Проверка истечения срока действия кода"""
        from django.utils import timezone
        return timezone.now() > self.expires_at

class UserActivity(models.Model):
    """Модель для хранения истории действий пользователя"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, verbose_name="Действие")
    target_type = models.CharField(max_length=15, choices=TARGET_TYPE_CHOICES, verbose_name="Тип объекта")

    target_title = models.CharField(max_length=255, verbose_name="Название объекта")

    guide = models.ForeignKey(Guide, on_delete=models.SET_NULL, null=True, blank=True)
    announcement = models.ForeignKey(Announcement, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата и время")

    class Meta:
        verbose_name = "Активность пользователя"
        verbose_name_plural = "История активности"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_action_display()} {self.get_target_type_display()}: '{self.target_title}' ({self.user.username})"