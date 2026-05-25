import json
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import FavoriteAnnouncement, FavoriteGuide, Announcement, Guide

@login_required
def favorites_page(request):
    favorite_announcements = FavoriteAnnouncement.objects.filter(
        user=request.user
    ).select_related('announcement', 'announcement__author').order_by('-added_at')
    favorite_guides = FavoriteGuide.objects.filter(
        user=request.user
    ).select_related('guide', 'guide__author').order_by('-added_at')

    return render(request, 'users/favorites.html', {
        'favorite_announcements': favorite_announcements,
        'favorite_guides': favorite_guides,
    })

@login_required
@require_POST
def toggle_favorite_announcement(request, announcement_id):
    try:
        announcement = get_object_or_404(Announcement, id=announcement_id)
        favorite, created = FavoriteAnnouncement.objects.get_or_create(
            user=request.user,
            announcement=announcement
        )
        if created:
            return JsonResponse({'success': True, 'added': True, 'message': 'Объявление добавлено в избранное'})
        favorite.delete()
        return JsonResponse({'success': True, 'added': False, 'message': 'Объявление удалено из избранного'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_POST
def toggle_favorite_guide(request, guide_id):
    try:
        guide = get_object_or_404(Guide, id=guide_id)
        favorite, created = FavoriteGuide.objects.get_or_create(
            user=request.user,
            guide=guide
        )
        if created:
            return JsonResponse({'success': True, 'added': True, 'message': 'Руководство добавлено в избранное'})
        favorite.delete()
        return JsonResponse({'success': True, 'added': False, 'message': 'Руководство удалено из избранного'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)