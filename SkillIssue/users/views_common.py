from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.permissions import BasePermission, SAFE_METHODS
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import ChatMessage, User, Profile, Guide, Announcement, UserActivity, Review
from .serializers import ChatMessageSerializer, ChatContactSerializer

class IsAuthorOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS: return True
        return obj.author == request.user or (request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.role in ['MODERATOR', 'ADMIN'])

class ChatContactsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        user = request.user
        messages = ChatMessage.objects.filter(Q(sender=user) | Q(receiver=user)).select_related("sender", "receiver", "sender__profile", "receiver__profile").order_by("-created_at")
        contacts_map = {}
        for msg in messages:
            other = msg.receiver if msg.sender_id == user.id else msg.sender
            data = contacts_map.setdefault(other.id, {"user_id": other.id, "username": other.username, "avatar": other.profile.avatar.url if hasattr(other, 'profile') and other.profile.avatar else None, "last_message": " ", "last_message_at": None, "unread_count": 0})
            if not data["last_message_at"] or msg.created_at > data["last_message_at"]:
                data["last_message"] = msg.message[:200] if msg.message.strip() else ("Картинка" if msg.image else "Без сообщений"); data["last_message_at"] = msg.created_at
            if msg.receiver_id == user.id and not msg.is_read: data["unread_count"] += 1
        contacts = sorted(contacts_map.values(), key=lambda i: i["last_message_at"] or timezone.now(), reverse=True)
        return Response(ChatContactSerializer(contacts, many=True).data)

class ChatMessagesView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, user_id):
        other = get_object_or_404(User, id=user_id)
        if other == request.user: return Response([])
        ChatMessage.objects.filter(sender=other, receiver=request.user, is_read=False).update(is_read=True)
        messages = ChatMessage.objects.filter((Q(sender=request.user, receiver=other) | Q(sender=other, receiver=request.user))).order_by("created_at")
        return Response(ChatMessageSerializer(messages, many=True, context={"request": request}).data)

class ChatSendMessageView(APIView):
    permission_classes = [permissions.IsAuthenticated]; parser_classes = [MultiPartParser, FormParser]
    def post(self, request):
        receiver_id, text, image = request.data.get("receiver_id"), (request.data.get("message") or " ").strip(), request.FILES.get("image")
        if not receiver_id: return Response({"error": "Не указан получатель"}, status=400)
        if not text and not image: return Response({"error": "Сообщение пусто"}, status=400)
        try: receiver_id = int(receiver_id)
        except: return Response({"error": "Некорректный ID"}, status=400)
        receiver = get_object_or_404(User, id=receiver_id)
        if receiver == request.user: return Response({"error": "Нельзя писать себе"}, status=400)
        message = ChatMessage.objects.create(sender=request.user, receiver=receiver, message=text, image=image)
        return Response(ChatMessageSerializer(message, context={"request": request}).data, status=201)

@api_view(['GET'])
def popular_items(request):
    try:
        guides_data = [{'id': g.id, 'title': g.title, 'image': request.build_absolute_uri(g.image.url) if g.image else None, 'author': g.author.username, 'rating': g.rating, 'url': f'/guides/{g.id}/', 'type': 'guide'} for g in Guide.objects.order_by('-rating', '-created_at')[:5]]
        announcements_data = [{'id': a.id, 'title': a.title, 'image': request.build_absolute_uri(a.image.url) if a.image else None, 'author': a.author.username, 'url': f'/announcements/{a.id}/', 'type': 'announcement'} for a in Announcement.objects.order_by('-created_at')[:5]]
        return Response({'guides': guides_data, 'announcements': announcements_data, 'items': (guides_data + announcements_data)[:6]})
    except Exception as e: return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def statistics(request):
    try: return Response({'guides': Guide.objects.count(), 'announcements': Announcement.objects.count(), 'users': User.objects.filter(is_active=True).count(), 'ratings': Review.objects.count() + ProfileReview.objects.count()})
    except Exception as e: return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def search_all_items(request):
    try:
        results = [{'title': (f"{p.user.first_name} {p.user.last_name}").strip() or p.user.username, 'type': 'профиль', 'url': f'/users/{p.user.username}/'} for p in Profile.objects.select_related('user')]
        results += [{'title': a.title, 'type': 'объявление', 'url': f'/announcements/{a.id}/'} for a in Announcement.objects]
        results += [{'title': g.title, 'type': 'руководство', 'url': f'/guides/{g.id}/'} for g in Guide.objects]
        return Response(results)
    except Exception as e: return Response({'error': str(e)}, status=500)

@swagger_auto_schema(method='get', operation_description="Поиск", manual_parameters=[openapi.Parameter('q', openapi.IN_QUERY, type=openapi.TYPE_STRING, required=True)], tags=['Поиск'])
@api_view(['GET'])
def search_items(request):
    query = request.GET.get('q', '').strip()
    if not query: return Response([])
    try:
        results, q_lower = [], query.lower()
        for p in Profile.objects.filter(Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query) | Q(user__username__icontains=query) | Q(bio__icontains=query)).select_related('user')[:30]:
            fn, un, bio = (f"{p.user.first_name} {p.user.last_name}").strip().lower(), p.user.username.lower(), (p.bio or '').lower()
            rel = (3 + (2 if un.startswith(q_lower) else 0) if q_lower in un else 0) + (2 + (1 if fn.startswith(q_lower) else 0) if q_lower in fn else 0) + (1 if q_lower in bio else 0)
            results.append({'title': fn.title() or p.user.username, 'type': 'профиль', 'url': f'/users/{p.user.username}/', 'relevance': rel})
        for a in Announcement.objects.filter(Q(title__icontains=query) | Q(description__icontains=query))[:30]:
            t, d = a.title.lower(), (a.description or '').lower()
            rel = (3 + (2 if t.startswith(q_lower) else 0) if q_lower in t else 0) + (1 if q_lower in d else 0)
            results.append({'title': a.title, 'type': 'объявление', 'url': f'/announcements/{a.id}/', 'relevance': rel})
        for g in Guide.objects.filter(Q(title__icontains=query) | Q(content__icontains=query))[:30]:
            t, c = g.title.lower(), (g.content or '').lower()
            rel = (3 + (2 if t.startswith(q_lower) else 0) if q_lower in t else 0) + (1 if q_lower in c else 0)
            results.append({'title': g.title, 'type': 'руководство', 'url': f'/guides/{g.id}/', 'relevance': rel})
        return Response([{'title': r['title'], 'type': r['type'], 'url': r['url']} for r in sorted(results, key=lambda x: x['relevance'], reverse=True)[:20]])
    except Exception as e: return Response({'error': str(e)}, status=500)

@api_view(['POST'])
def set_language(request):
    language = request.data.get('language', '').upper()
    if language not in ['RU', 'EN']: return Response({'error': 'Неверный код языка'}, status=400)
    response = Response({'success': True, 'language': language})
    response.set_cookie('lang', language, max_age=365*24*60*60, httponly=False, samesite='Lax', secure=False)
    return response

@api_view(['GET'])
def user_activities(request, username):
    try:
        user_obj = get_object_or_404(User, username=username)
        activities = UserActivity.objects.filter(user=user_obj).order_by('-created_at')[:50]
        data = []
        for a in activities:
            url = f'/guides/{a.guide.id}/' if a.target_type == 'GUIDE' and a.guide else (f'/announcements/{a.announcement.id}/' if a.target_type == 'ANNOUNCEMENT' and a.announcement else None)
            local_time = timezone.localtime(a.created_at)
            data.append({'id': a.id, 'action': a.action, 'action_display': a.get_action_display(), 'target_type': a.target_type, 'target_type_display': a.get_target_type_display(), 'target_title': a.target_title, 'created_at': local_time.strftime('%d.%m.%Y %H:%M'), 'time': local_time.strftime('%H:%M'), 'url': url})
        return Response(data)
    except Exception as e: return Response({'error': str(e)}, status=500)