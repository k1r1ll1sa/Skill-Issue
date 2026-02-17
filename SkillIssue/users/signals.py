from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db.models import Avg
from .models import Profile, GuideRating, Announcement, UserActivity, Guide


@receiver([post_save, post_delete], sender=GuideRating)
def update_profile_rating(sender, instance, **kwargs):
    guide = instance.guide
    author = guide.author

    try:
        profile = author.profile
    except Profile.DoesNotExist:
        return

    avg_rating = GuideRating.objects.filter(
        guide__author=author
    ).aggregate(Avg('rating'))['rating__avg']

    profile.rating = round(avg_rating or 0.00, 2)
    profile.save(update_fields=['rating'])

@receiver(pre_save, sender=Guide)
def detect_guide_update(sender, instance, **kwargs):
    if instance.pk is None:
        return  # Это создание — будет обработано post_save

    try:
        old = Guide.objects.get(pk=instance.pk)
        # Проверяем, изменились ли значимые поля
        fields_to_watch = ['title', 'content', 'tags', 'image']
        has_significant_change = any(
            getattr(old, f) != getattr(instance, f)
            for f in fields_to_watch
        )
        instance._significant_change = has_significant_change
    except Guide.DoesNotExist:
        instance._significant_change = True

@receiver(post_save, sender=Guide)
def log_guide_creation_update(sender, instance, created, **kwargs):
    if created:
        action = 'CREATE'
    elif getattr(instance, '_significant_change', True):
        action = 'UPDATE'
    else:
        return  # Не логируем, если изменение — только рейтинг

    UserActivity.objects.create(
        user=instance.author,
        action=action,
        target_type='GUIDE',
        target_title=instance.title,
        guide=instance
    )

@receiver(post_delete, sender=Guide)
def log_guide_deletion(sender, instance, **kwargs):
    """
    Логирует удаление руководства.
    Сохраняет название, даже если объект уже удалён из БД.
    """
    UserActivity.objects.create(
        user=instance.author,
        action='DELETE',
        target_type='GUIDE',
        target_title=instance.title
        # Поле 'guide' остаётся null, так как объект удалён
    )


@receiver(post_save, sender=Announcement)
def log_announcement_creation_update(sender, instance, created, **kwargs):
    """
    Логирует создание или обновление объявления.
    """
    action = 'CREATE' if created else 'UPDATE'
    UserActivity.objects.create(
        user=instance.author,
        action=action,
        target_type='ANNOUNCEMENT',
        target_title=instance.title,
        announcement=instance  # Опциональная ссылка
    )


@receiver(post_delete, sender=Announcement)
def log_announcement_deletion(sender, instance, **kwargs):
    """
    Логирует удаление объявления.
    """
    UserActivity.objects.create(
        user=instance.author,
        action='DELETE',
        target_type='ANNOUNCEMENT',
        target_title=instance.title
    )