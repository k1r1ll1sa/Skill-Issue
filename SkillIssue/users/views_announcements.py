from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView
from rest_framework import status, permissions, viewsets
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db.models import Count, Prefetch, Q, F
from .models import Announcement, FavoriteAnnouncement, AnnouncementComment, AnnouncementCommentRating, AnnouncementCommentReply, AnnouncementCommentReplyRating
from .serializers import AnnouncementSerializer
from .utils import filter_text

class AnnouncementListView(ListView):
    model = Announcement
    template_name = 'users/announcement.html'
    context_object_name = 'announcements'
    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))
            query_lower = search_query.lower()
            announcements = list(queryset)
            for ann in announcements:
                relevance = 0
                title_lower = ann.title.lower()
                desc_lower = (ann.description or '').lower()
                if title_lower.startswith(query_lower): relevance += 5
                elif query_lower in title_lower: relevance += 3
                if query_lower in desc_lower: relevance += 1
                ann.relevance = relevance
            announcements.sort(key=lambda x: x.relevance, reverse=True)
            return announcements[:20]
        return queryset.order_by('-created_at')

@login_required
def create_announcement_view(request):
    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")
        tags_raw = request.POST.get("tags", "")
        tags_list = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]
        image = request.FILES.get("image")
        if title and description:
            Announcement.objects.create(title=title, description=description, author=request.user, tags=tags_list, image=image)
            return redirect("announcements_list")
    return render(request, "users/create_announcement.html")

def announcement_detail(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)
    sort_by = request.GET.get('sort', 'new')
    comments = announcement.comments.select_related('author', 'author__profile').annotate(
        likes_count=Count('ratings', filter=Q(ratings__is_like=True)),
        dislikes_count=Count('ratings', filter=Q(ratings__is_like=False))
    )
    if sort_by == 'Popular':
        comments = comments.annotate(net_rating=F('likes_count') - F('dislikes_count')).order_by('-net_rating', '-created_at')
    else:
        comments = comments.order_by('-created_at')
    replies_qs = AnnouncementCommentReply.objects.select_related('author', 'author__profile').annotate(
        likes_count=Count('ratings', filter=Q(ratings__is_like=True)),
        dislikes_count=Count('ratings', filter=Q(ratings__is_like=False))
    ).order_by('created_at')
    comments = comments.prefetch_related(Prefetch('replies', queryset=replies_qs))
    is_favorited, user_liked, user_disliked = False, set(), set()
    user_liked_replies, user_disliked_replies = set(), set()
    if request.user.is_authenticated:
        is_favorited = FavoriteAnnouncement.objects.filter(user=request.user, announcement=announcement).exists()
        for r in AnnouncementCommentRating.objects.filter(comment__in=comments, user=request.user):
            (user_liked if r.is_like else user_disliked).add(r.comment_id)
        all_reply_ids = [reply.id for c in comments for reply in c.replies.all()]
        if all_reply_ids:
            for r in AnnouncementCommentReplyRating.objects.filter(reply_id__in=all_reply_ids, user=request.user):
                (user_liked_replies if r.is_like else user_disliked_replies).add(r.reply_id)
    return render(request, 'users/announcement_detail.html', {
        'announcement': announcement, 'comments': comments, 'is_favorited': is_favorited,
        'user_liked': user_liked, 'user_disliked': user_disliked,
        'user_liked_replies': user_liked_replies, 'user_disliked_replies': user_disliked_replies, 'sort_by': sort_by
    })

@login_required
def edit_announcement(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)
    is_moderator = hasattr(request.user, 'profile') and request.user.profile.role == 'MODERATOR'
    if request.user != announcement.author and not is_moderator:
        return redirect('announcement_detail', announcement_id=announcement_id)
    tags_string = ', '.join(announcement.tags) if isinstance(announcement.tags, list) else str(announcement.tags) if announcement.tags else ''
    return render(request, 'users/announcement_edit.html', {'announcement': announcement, 'tags_string': tags_string})

@login_required
def update_announcement(request, announcement_id):
    if request.method == 'POST':
        announcement = get_object_or_404(Announcement, id=announcement_id)
        if request.user != announcement.author:
            return redirect('announcement_detail', announcement_id=announcement_id)
        update_fields = ['title', 'description', 'tags']
        announcement.title = request.POST.get('title')
        announcement.description = request.POST.get('description')
        announcement.tags = request.POST.get('tags', '')
        if 'image' in request.FILES:
            announcement.image = request.FILES['image']
            update_fields.append('image')
        announcement.save(update_fields=update_fields)
        return redirect('announcement_detail', announcement_id=announcement_id)
    return redirect('edit_announcement', announcement_id=announcement_id)

class AnnouncementViewSet(viewsets.ModelViewSet):
    queryset = Announcement.objects.all().order_by("-created_at")
    serializer_class = AnnouncementSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    def perform_create(self, serializer): serializer.save(author=self.request.user)

@swagger_auto_schema(method='get', operation_description="Фильтрация объявлений", tags=['Объявления'])
@api_view(['GET'])
def filter_announcements(request):
    try:
        queryset = Announcement.objects.all()
        search_query = request.GET.get('search', '').strip()
        if search_query: queryset = queryset.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))
        tags_query = request.GET.get('tags', '').strip()
        if tags_query:
            tags_list = [tag.strip().lower() for tag in tags_query.split(',') if tag.strip()]
            if tags_list:
                filtered_ids = [a.id for a in queryset.iterator() if any(t in [str(x).lower().strip() for x in (a.tags or []) if x] for t in tags_list)]
                queryset = queryset.filter(id__in=filtered_ids) if filtered_ids else queryset.none()
        date_filter = request.GET.get('date_filter', '').strip()
        if date_filter.isdigit(): queryset = queryset.filter(created_at__date__gte=timezone.localdate() - __import__('datetime').timedelta(days=int(date_filter)))
        if search_query:
            announcements = list(queryset); query_lower = search_query.lower()
            for a in announcements:
                rel = 0; t = a.title.lower(); d = (a.description or '').lower()
                if t.startswith(query_lower): rel += 5
                elif query_lower in t: rel += 3
                if query_lower in d: rel += 1
                a.relevance = rel
            announcements.sort(key=lambda x: x.relevance, reverse=True); announcements = announcements[:20]
            return Response({'count': len(announcements), 'results': AnnouncementSerializer(announcements, many=True, context={'request': request}).data})
        return Response({'count': queryset.count(), 'results': AnnouncementSerializer(queryset.order_by('-created_at'), many=True, context={'request': request}).data})
    except Exception as e: return Response({'error': str(e)}, status=500)