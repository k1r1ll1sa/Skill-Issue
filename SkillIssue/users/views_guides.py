import re
import os
import markdown
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import ListView
from rest_framework import status, permissions, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db.models import Avg, Count, Prefetch, Q, F
from django.utils.safestring import mark_safe
from rest_framework.views import APIView

from .models import Guide, GuideRating, Review, GuideReviewRating, ReviewReply, ReviewReplyRating
from .daos import GuideDAO
from .serializers import GuideSerializer
from .forms import GuideForm
from .utils import filter_text

def convert_youtube_links_to_embed(content):
    pattern_standard = r'https?://(?:www.)?youtube.com/watch?v=([a-zA-Z0-9_-]+)([^\s"\'<>])'
    pattern_shorts = r'https?://(?:www.)?youtube.com/shorts/([a-zA-Z0-9_-]+)([^\s"\'<>])'
    def replace_standard(match):
        video_id = match.group(1)
        params = match.group(2) or ''
        if params.startswith('&'): params = '?' + params[1:]
        elif params and not params.startswith('?'): params = '?' + params
        return f'https://www.youtube.com/embed/{video_id}{params}'
    content = re.sub(pattern_standard, replace_standard, content)
    content = re.sub(pattern_shorts, lambda m: f'https://www.youtube.com/embed/{m.group(1)}', content)
    return content

def convert_youtube_embeds_to_html(content):
    pattern_shorts = r'https://www.youtube.com/embed/([a-zA-Z0-9_-]+)([^\s"\'<>])#shorts'
    pattern_normal = r'https://www.youtube.com/embed/([a-zA-Z0-9_-]+)([^\s"\'<>])'
    def replace_with_iframe(match, is_shorts):
        video_id = match.group(1)
        params = match.group(2) or ''
        return f'''<div class="youtube-embed-wrapper"><iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}{'' if is_shorts else params}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen loading="lazy"></iframe></div><br>'''
    content = re.sub(pattern_shorts, lambda m: replace_with_iframe(m, True), content)
    content = re.sub(pattern_normal, lambda m: replace_with_iframe(m, False), content)
    return content

class GuideListView(ListView):
    model = Guide
    template_name = 'users/guides.html'
    context_object_name = 'popular_guides'
    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(Q(title__icontains=search_query) | Q(content__icontains=search_query))
            query_lower = search_query.lower()
            guides = list(queryset)
            for guide in guides:
                relevance = 0
                title_lower = guide.title.lower()
                content_lower = (guide.content or '').lower()
                if title_lower.startswith(query_lower): relevance += 5
                elif query_lower in title_lower: relevance += 3
                if query_lower in content_lower: relevance += 1
                guide.relevance = relevance
            guides.sort(key=lambda x: x.relevance, reverse=True)
            return guides[:20]
        return queryset.order_by('-rating')[:6]
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.request.GET.get('search'):
            context['top_guides'] = Guide.objects.order_by('-rating')[:6]
        return context

@login_required
@xframe_options_exempt
def create_guide(request):
    guide_id = request.GET.get('id')
    guide = None
    if guide_id:
        guide = get_object_or_404(Guide, id=guide_id)
        is_moderator = hasattr(request.user, 'profile') and request.user.profile.role == 'MODERATOR'
        if guide.author != request.user and not is_moderator:
            return redirect('guides_list')
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        tags_raw = request.POST.get('tags', '').strip()
        image = request.FILES.get('image')
        tags_list = [tag.strip() for tag in tags_raw.split(',') if tag.strip()] if tags_raw else []
        content = convert_youtube_links_to_embed(content)
        if guide:
            update_fields = ['title', 'content', 'tags']
            guide.title, guide.content, guide.tags = title, content, tags_list
            if image:
                guide.image = image
                update_fields.append('image')
            guide.save(update_fields=update_fields)
            guide_obj = guide
        else:
            guide_obj = Guide.objects.create(title=title, content=content, author=request.user, tags=tags_list, image=image)
        for key, file in request.FILES.items():
            if key.startswith('image_'):
                from django.core.files.storage import default_storage
                from django.core.files.base import ContentFile
                timestamp = int(timezone.now().timestamp() * 1000)
                original_name = file.name
                _, ext = os.path.splitext(original_name)
                unique_filename = f'image_{timestamp}{ext}'
                filename = default_storage.save(f'guides/{unique_filename}', ContentFile(file.read()))
                file_url = default_storage.url(filename)
                content = content.replace(f'({original_name})', f'({file_url})')
                content = re.sub(rf'\(image_\d+_{re.escape(original_name)}\)', f'({file_url})', content)
        if content != guide_obj.content:
            guide_obj.content = content
            guide_obj.save()
        return redirect('guide_detail', pk=guide_obj.id)
    return render(request, 'users/create_guides.html', {'form': GuideForm(instance=guide), 'guide': guide})

@xframe_options_exempt
def guide_detail(request, pk):
    guide = get_object_or_404(Guide, pk=pk)
    content = convert_youtube_embeds_to_html(convert_youtube_links_to_embed(guide.content or ""))
    html = markdown.markdown(content, extensions=['extra', 'codehilite'], output_format='html5')
    html = re.sub(r'src="(?!https?://|/)([^"]+)"', r'src="/media/guides/\1"', html, flags=re.IGNORECASE)
    guide_content_html = mark_safe(html)
    sort_by = request.GET.get('sort', 'new')
    reviews = guide.reviews.select_related("author", "author__profile").annotate(
        likes_count=Count('ratings', filter=Q(ratings__is_like=True)),
        dislikes_count=Count('ratings', filter=Q(ratings__is_like=False))
    ).prefetch_related(Prefetch('replies', queryset=ReviewReply.objects.select_related('author', 'author__profile').annotate(
        likes_count=Count('ratings', filter=Q(ratings__is_like=True)),
        dislikes_count=Count('ratings', filter=Q(ratings__is_like=False))
    ).order_by('created_at')))
    if sort_by == 'Popular':
        reviews = reviews.annotate(net_rating=F('likes_count') - F('dislikes_count')).order_by('-net_rating', '-created_at')
    else:
        reviews = reviews.order_by('-created_at')
    user_liked, user_disliked, user_liked_replies, user_disliked_replies = set(), set(), set(), set()
    if request.user.is_authenticated:
        for r in GuideReviewRating.objects.filter(review__in=reviews, user=request.user):
            (user_liked if r.is_like else user_disliked).add(r.review_id)
        all_reply_ids = [reply.id for review in reviews for reply in review.replies.all()]
        if all_reply_ids:
            for r in ReviewReplyRating.objects.filter(reply_id__in=all_reply_ids, user=request.user):
                (user_liked_replies if r.is_like else user_disliked_replies).add(r.reply_id)
    return render(request, 'users/guide_detail.html', {
        'guide': guide, 'guide_content_html': guide_content_html, 'reviews': reviews, 'is_favorited': False,
        'user_liked': user_liked, 'user_disliked': user_disliked,
        'user_liked_replies': user_liked_replies, 'user_disliked_replies': user_disliked_replies, 'sort_by': sort_by
    })

@swagger_auto_schema(operation_description="Оценить руководство (гайд) от 1 до 5", tags=['Руководства'])
class GuideRateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, guide_id):
        guide = get_object_or_404(Guide, id=guide_id)
        rating_value = int(request.data.get('rating', 0))
        if not 1 <= rating_value <= 5: return Response({'error': 'Рейтинг должен быть от 1 до 5'}, status=400)
        GuideRating.objects.update_or_create(guide=guide, reviewer=request.user, defaults={'rating': rating_value})
        guide.rating = int(round(guide.ratings.aggregate(avg=Avg('rating'))['avg'] or 0))
        guide.save(update_fields=['rating'])
        profile = guide.author.profile
        profile.rating = int(round(Guide.objects.filter(author=guide.author).aggregate(avg=Avg('rating'))['avg'] or 0))
        profile.save(update_fields=['rating'])
        return Response({"guide_average_rating": guide.rating, "profile_average_rating": profile.rating})

class GuideViewSet(viewsets.ModelViewSet):
    queryset = Guide.objects.all().order_by('-rating', '-created_at')
    serializer_class = GuideSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    @action(detail=False, methods=['get'], url_path='dao-guides')
    def get_guides_from_dao(self, request):
        return Response(GuideSerializer(GuideDAO.get_all(), many=True).data)
    @action(detail=False, methods=['get'], url_path='dto-guides')
    def get_dto_guides(self, request):
        dtos = GuideDAO.get_guides_dto()
        return Response([{"id": d.id, "title": d.title, "author": d.author_username, "rating": d.rating} for d in dtos])
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

@swagger_auto_schema(method='get', operation_description="Фильтрация руководств", tags=['Руководства'])
@api_view(['GET'])
def filter_guides(request):
    try:
        queryset = Guide.objects.all()
        search_query = request.GET.get('search', '').strip()
        if search_query: queryset = queryset.filter(Q(title__icontains=search_query) | Q(content__icontains=search_query))
        tags_query = request.GET.get('tags', '').strip()
        if tags_query:
            tags_list = [tag.strip().lower() for tag in tags_query.split(',') if tag.strip()]
            if tags_list:
                filtered_ids = [g.id for g in queryset.iterator() if any(t in [str(x).lower().strip() for x in (g.tags or []) if x] for t in tags_list)]
                queryset = queryset.filter(id__in=filtered_ids) if filtered_ids else queryset.none()
        date_filter = request.GET.get('date_filter', '').strip()
        if date_filter.isdigit(): queryset = queryset.filter(created_at__date__gte=timezone.localdate() - __import__('datetime').timedelta(days=int(date_filter)))
        if search_query:
            guides = list(queryset); query_lower = search_query.lower()
            for g in guides:
                rel = 0; t = g.title.lower(); c = (g.content or '').lower()
                if t.startswith(query_lower): rel += 5
                elif query_lower in t: rel += 3
                if query_lower in c: rel += 1
                g.relevance = rel
            guides.sort(key=lambda x: x.relevance, reverse=True); guides = guides[:20]
            return Response({'count': len(guides), 'results': GuideSerializer(guides, many=True, context={'request': request}).data})
        return Response({'count': queryset.count(), 'results': GuideSerializer(queryset.order_by('-rating', '-created_at'), many=True, context={'request': request}).data})
    except Exception as e: return Response({'error': str(e)}, status=500)