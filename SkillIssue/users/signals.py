from django.db.models.signals import post_save, post_delete
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

@receiver(post_save, sender=Guide)
def log_guide_creation_update(sender, instance, created, **kwargs):
    """
    Логирует создание или обновление руководства.
    Создает запись активности только при реальном изменении полей объекта.
    """
    if created:
        # При создании всегда логируем
        action = 'CREATE'
        UserActivity.objects.create(
            user=instance.author,
            action=action,
            target_type='GUIDE',
            target_title=instance.title,
            guide=instance
        )
    else:
        # При обновлении проверяем, были ли изменены важные поля
        update_fields = kwargs.get('update_fields')
        if update_fields:
            # Проверяем, изменялись ли важные поля (не только служебные)
            important_fields = {'title', 'content', 'image', 'tags'}
            if any(field in update_fields for field in important_fields):
                UserActivity.objects.create(
                    user=instance.author,
                    action='UPDATE',
                    target_type='GUIDE',
                    target_title=instance.title,
                    guide=instance
                )
        else:
            # Если update_fields не указан, проверяем через сравнение с БД
            # Но это может быть неэффективно, поэтому создаем запись только если явно указаны поля
            pass


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
    Создает запись активности только при реальном изменении полей объекта.
    """
    if created:
        # При создании всегда логируем
        action = 'CREATE'
        UserActivity.objects.create(
            user=instance.author,
            action=action,
            target_type='ANNOUNCEMENT',
            target_title=instance.title,
            announcement=instance
        )
    else:
        # При обновлении проверяем, были ли изменены важные поля
        update_fields = kwargs.get('update_fields')
        if update_fields:
            # Проверяем, изменялись ли важные поля (не только служебные)
            important_fields = {'title', 'description', 'image', 'tags'}
            if any(field in update_fields for field in important_fields):
                UserActivity.objects.create(
                    user=instance.author,
                    action='UPDATE',
                    target_type='ANNOUNCEMENT',
                    target_title=instance.title,
                    announcement=instance
                )
        # Если update_fields не указан, не создаем запись активности
        # чтобы избежать ложных срабатываний при автоматических сохранениях


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