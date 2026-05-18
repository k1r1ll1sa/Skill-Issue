from django.contrib import admin
from .models import Profile, Guide, Review, GuideRating, BlacklistWord


@admin.register(Guide)
class GuideAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "created_at", "rating")
    list_filter = ("created_at", "author")
    search_fields = ("title", "content", "author__username")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "rating", "created_at", "is_blocked", "blocked_at")
    list_filter = ("is_blocked", "role", "created_at")
    search_fields = ("user__username",)
    readonly_fields = ['blocked_at']
    fieldsets = (
        ('Основное', {
            'fields': ('user', 'avatar', 'bio', 'rating', 'allow_reviews', 'role')
        }),
        ('Блокировка', {
            'fields': ('is_blocked', 'blocked_reason'),
            'classes': ('collapse',)
        }),
        ('Соцсети и ссылки', {
            'fields': ('telegram', 'github', 'vk', 'youtube', 'website'),
            'classes': ('collapse',)
        }),
        ('Баннер', {
            'fields': ('banner_style', 'banner_image'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("guide", "author", "stars", "created_at")
    list_filter = ("stars", "created_at")
    search_fields = ("guide__title", "author__username", "text")
    readonly_fields = ['created_at']  # Исправлено: было 'blocked_at'

@admin.register(GuideRating)
class GuideRatingAdmin(admin.ModelAdmin):
    list_display = ("guide", "reviewer", "rating", "created_at")
    list_filter = ("rating",)


@admin.register(BlacklistWord)
class BlacklistWordAdmin(admin.ModelAdmin):
    list_display = ('word', 'replacement', 'is_active', 'case_sensitive', 'created_at')
    list_filter = ('is_active', 'case_sensitive', 'created_at')
    search_fields = ('word',)
    ordering = ('word',)

    fieldsets = (
        ('Основное', {
            'fields': ('word', 'replacement', 'is_active', 'case_sensitive')
        }),
        ('Информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at',)
