import re

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.views.generic import ListView
from rest_framework.decorators import action
from rest_framework import status, permissions, generics, viewsets, serializers
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import BasePermission
from rest_framework.decorators import api_view
import markdown
from rest_framework.parsers import MultiPartParser, FormParser
from .daos import GuideDAO
from django.db.models import Avg
from django.db.models import Q
from django.utils.safestring import mark_safe
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
import random
import string


from .models import Profile, GuideRating, Review, Guide, ProfileReview, Announcement, AnnouncementComment, EmailVerificationCode, ChatMessage, UserActivity
from .serializers import RegisterSerializer, UserProfileSerializer, ReviewSerializer, GuideSerializer, \
    AnnouncementSerializer, ChatMessageSerializer, ChatContactSerializer, ProfileCommentSerializer
from .forms import GuideForm


def main_page(request):
    return render(request, "users/main.html")


def register_page(request):
    return render(request, "users/reg.html")


def login_page(request):
    return render(request, "users/log.html")


def profile_page(request, username):
    user_obj = get_object_or_404(User, username=username)
    profile = user_obj.profile
    guides = Guide.objects.filter(author=user_obj).order_by('-created_at')
    announcements = Announcement.objects.filter(author=user_obj).order_by('-created_at')
    reviews = ProfileReview.objects.filter(profile=profile).order_by('-created_at')
    activities = UserActivity.objects.filter(user=user_obj).order_by('-created_at')[:20]

    return render(request, "users/profile.html", {
        "username": username,
        "profile": profile,
        "guides": guides,
        "reviews": reviews,
        "announcements": announcements,
        "activities": activities,
    })


def logout_view(request):
    logout(request)
    return redirect("main_page")


def favorites_page(request):
    return render(request, "users/favorites.html", {
        "favorite_guides": [],
        "favorite_announcements": [],
    })


def profile_guides_api(username):
    user_obj = get_object_or_404(User, username=username)
    guides = Guide.objects.filter(author=user_obj).order_by('-created_at')
    guides_data = [
        {
            "id": g.id,
            "title": g.title,
            "image": g.image.url if g.image else None,
            "created_at": g.created_at,
        }
        for g in guides
    ]
    return JsonResponse({"guides": guides_data})


class GuideListView(ListView):
    model = Guide
    template_name = 'users/guides.html'
    context_object_name = 'popular_guides'

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search')

        if search_query:
            # Фильтруем по названию руководства
            queryset = queryset.filter(title__icontains=search_query)
        else:
            # Если нет поиска, показываем популярные (с высоким рейтингом)
            queryset = queryset.order_by('-rating')[:6]

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_query = self.request.GET.get('search')

        if not search_query:
            context['top_guides'] = Guide.objects.order_by('-rating')[:6]

        return context


class AnnouncementListView(ListView):
    model = Announcement
    template_name = 'users/announcement.html'
    context_object_name = 'announcements'

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(title__icontains=search_query)
        return queryset

@login_required
def create_guide(request):
    guide_id = request.GET.get('id')
    guide = None
    if guide_id:
        guide = get_object_or_404(Guide, id=guide_id)
        if guide.author != request.user:
            return redirect('guides_list')

    if request.method == 'POST':
        # Обрабатываем данные формы
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        tags_raw = request.POST.get('tags', '').strip()
        image = request.FILES.get('image')
        
        # Обрабатываем теги
        tags_list = []
        if tags_raw:
            tags_list = [tag.strip() for tag in tags_raw.split(',') if tag.strip()]
        
        if guide:
            # Редактирование существующего руководства
            update_fields = ['title', 'content', 'tags']
            guide.title = title
            guide.content = content
            guide.tags = tags_list
            if image:
                guide.image = image
                update_fields.append('image')
            guide.save(update_fields=update_fields)
            guide_obj = guide
        else:
            # Создание нового руководства
            guide_obj = Guide.objects.create(
                title=title,
                content=content,
                author=request.user,
                tags=tags_list,
                image=image if image else None
            )

        # Обрабатываем изображения в контенте
        content = guide_obj.content
        for key, file in request.FILES.items():
            if key.startswith('image_'):
                from django.core.files.storage import default_storage
                from django.core.files.base import ContentFile

                filename = default_storage.save(f'guides/{file.name}', ContentFile(file.read()))
                file_url = default_storage.url(filename)

                content = content.replace(f'({file.name})', f'({file_url})')
                content = content.replace(f'(1761295916746_{file.name})', f'({file_url})')
        
        if content != guide_obj.content:
            guide_obj.content = content
            guide_obj.save()

        return redirect('guide_detail', pk=guide_obj.id)
    else:
        form = GuideForm(instance=guide)

    return render(request, 'users/create_guides.html', {'form': form, 'guide': guide})


def guide_detail(request, pk):
    guide = get_object_or_404(Guide, pk=pk)

    html = markdown.markdown(guide.content or "", extensions=['extra'])

    html = re.sub(
        r'<img\s+[^>]*src="(?!https?://|/|/media/)([^"]+)"',
        r'<img src="/media/guides/\1"',
        html
    )

    guide_content_html = mark_safe(html)
    reviews = guide.reviews.select_related("author", "author__profile").order_by("-created_at")

    return render(request, 'users/guide_detail.html', {
        'guide': guide,
        'guide_content_html': guide_content_html,
        'reviews': reviews,
    })


def announcement_detail(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)
    comments = announcement.comments.all().select_related('author')

    context = {
        'announcement_id': announcement_id,
        'announcement': announcement,
        'comments': comments,
    }
    return render(request, 'users/announcement_detail.html', context)


@login_required
def profile_edit(request):
    profile = request.user.profile
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        description = request.POST.get("description", "").strip()
        avatar = request.FILES.get("avatar")

        if username:
            request.user.username = username
            request.user.save()

        profile.bio = description
        if avatar:
            profile.avatar = avatar
        profile.save()

        return redirect(f"{request.path}?updated=1")

    return render(request, "users/profile_edit.html", {"profile": profile, "user": request.user})

@login_required
def edit_announcement(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)

    if request.user != announcement.author:
        return redirect('announcement_detail', announcement_id=announcement_id)

    tags_string = ''
    if announcement.tags:
        if isinstance(announcement.tags, list):
            tags_string = ', '.join(announcement.tags)
        else:
            tags_string = str(announcement.tags)

    context = {
        'announcement': announcement,
        'tags_string': tags_string,
    }
    return render(request, 'users/announcement_edit.html', context)

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


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_description="Регистрация нового пользователя. После регистрации на email будет отправлен код подтверждения.",
        request_body=RegisterSerializer,
        responses={
            201: openapi.Response(
                description="Пользователь успешно зарегистрирован, код подтверждения отправлен на email",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'email': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Ошибка валидации данных"
        },
        tags=['Аутентификация']
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data.get('email')
            if not email:
                return Response({"error": "Email обязателен для регистрации"}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Проверка существования пользователя с таким email
            if User.objects.filter(email=email).exists():
                return Response({"error": "Пользователь с таким email уже существует"}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Создаем пользователя, но делаем его неактивным до подтверждения email
            user = serializer.save()
            user.is_active = False
            user.save()
            
            # Генерируем код подтверждения
            code = ''.join(random.choices(string.digits, k=6))
            expires_at = timezone.now() + timedelta(minutes=15)
            
            # Сохраняем код в базе данных
            EmailVerificationCode.objects.create(
                user=user,
                code=code,
                email=email,
                expires_at=expires_at
            )
            
            # Отправляем код на email
            send_mail(
                subject='Подтверждение регистрации - Skill Issue',
                message=f'Ваш код подтверждения: {code}\nКод действителен в течение 15 минут.',
                from_email=None,  # Используется DEFAULT_FROM_EMAIL из settings
                recipient_list=[email],
                fail_silently=False,
            )
            
            return Response({
                "message": "Пользователь зарегистрирован. Код подтверждения отправлен на email.",
                "id": user.id,
                "email": email
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # Отключаем CSRF для JWT логина

    @swagger_auto_schema(
        operation_description="Авторизация пользователя с использованием JWT токенов",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'password'],
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='Имя пользователя'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='Пароль'),
            }
        ),
        responses={
            200: openapi.Response(
                description="Успешная авторизация",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'access': openapi.Schema(type=openapi.TYPE_STRING, description='JWT Access токен'),
                        'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='JWT Refresh токен'),
                        'username': openapi.Schema(type=openapi.TYPE_STRING),
                        'email': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Не указаны логин или пароль",
            401: "Неверные данные для входа или email не подтвержден"
        },
        tags=['Аутентификация']
    )
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response({"error": "Введите логин и пароль"}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({"error": "Неверные данные"}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Проверяем, подтвержден ли email
        if not user.is_active:
            return Response({"error": "Email не подтвержден. Проверьте почту и подтвердите регистрацию."}, 
                          status=status.HTTP_401_UNAUTHORIZED)

        # Генерируем JWT токены
        refresh = RefreshToken.for_user(user)

        # Создаем сессионную авторизацию, чтобы /api/me работало и по cookie
        login(request, user)
        
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "username": user.username,
            "email": user.email,
        }, status=status.HTTP_200_OK)


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_description="Подтверждение email пользователя по коду",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email', 'code'],
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, description='Email пользователя'),
                'code': openapi.Schema(type=openapi.TYPE_STRING, description='Код подтверждения из письма'),
            }
        ),
        responses={
            200: openapi.Response(
                description="Email успешно подтвержден",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'username': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Неверный код или код истек",
            404: "Пользователь не найден"
        },
        tags=['Аутентификация']
    )
    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')

        if not email or not code:
            return Response({"error": "Укажите email и код"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Пользователь не найден"}, status=status.HTTP_404_NOT_FOUND)

        # Ищем актуальный код подтверждения
        verification = EmailVerificationCode.objects.filter(
            user=user,
            email=email,
            code=code,
            is_used=False
        ).order_by('-created_at').first()

        if not verification:
            return Response({"error": "Неверный код подтверждения"}, status=status.HTTP_400_BAD_REQUEST)

        if verification.is_expired():
            return Response({"error": "Код подтверждения истек. Запросите новый код."}, 
                          status=status.HTTP_400_BAD_REQUEST)

        # Помечаем код как использованный
        verification.is_used = True
        verification.save()

        # Активируем пользователя
        user.is_active = True
        user.save()

        return Response({
            "message": "Email успешно подтвержден",
            "username": user.username
        }, status=status.HTTP_200_OK)


class ResendVerificationCodeView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_description="Повторная отправка кода подтверждения email",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email'],
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, description='Email пользователя'),
            }
        ),
        responses={
            200: openapi.Response(
                description="Код подтверждения отправлен повторно",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Пользователь не найден или email уже подтвержден"
        },
        tags=['Аутентификация']
    )
    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response({"error": "Укажите email"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Пользователь не найден"}, status=status.HTTP_400_BAD_REQUEST)

        if user.is_active:
            return Response({"error": "Email уже подтвержден"}, status=status.HTTP_400_BAD_REQUEST)

        # Генерируем новый код
        code = ''.join(random.choices(string.digits, k=6))
        expires_at = timezone.now() + timedelta(minutes=15)

        # Сохраняем код в базе данных
        EmailVerificationCode.objects.create(
            user=user,
            code=code,
            email=email,
            expires_at=expires_at
        )

        # Отправляем код на email
        send_mail(
            subject='Подтверждение регистрации - Skill Issue',
            message=f'Ваш код подтверждения: {code}\nКод действителен в течение 15 минут.',
            from_email=None,
            recipient_list=[email],
            fail_silently=False,
        )

        return Response({
            "message": "Код подтверждения отправлен повторно на email"
        }, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Получить информацию о текущем авторизованном пользователе",
        responses={
            200: openapi.Response(
                description="Информация о пользователе",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'username': openapi.Schema(type=openapi.TYPE_STRING),
                        'email': openapi.Schema(type=openapi.TYPE_STRING),
                        'is_active': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'date_joined': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME),
                    }
                )
            ),
            401: "Пользователь не авторизован"
        },
        tags=['Пользователи']
    )
    def get(self, request):
        user = request.user
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "date_joined": user.date_joined,
        })


class UserProfileDetailView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer

    @swagger_auto_schema(
        operation_description="Получить профиль пользователя по имени пользователя",
        responses={
            200: UserProfileSerializer,
            404: "Профиль не найден"
        },
        tags=['Профили']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_object(self):
        username = self.kwargs.get("username")
        return get_object_or_404(Profile, user__username=username)


class ReviewCreateView(generics.CreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Создать отзыв на руководство (гайд)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['guide_id', 'text', 'stars'],
            properties={
                'guide_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID руководства'),
                'text': openapi.Schema(type=openapi.TYPE_STRING, description='Текст отзыва'),
                'stars': openapi.Schema(type=openapi.TYPE_INTEGER, description='Рейтинг от 1 до 5', minimum=1, maximum=5),
            }
        ),
        responses={
            201: ReviewSerializer,
            400: "Ошибка валидации или отзыв уже существует"
        },
        tags=['Отзывы']
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        guide_id = self.request.data.get("guide_id")
        stars = self.request.data.get("stars")  # получаем рейтинг
        if not stars:
            stars = 0

        guide = get_object_or_404(Guide, id=guide_id)

        # Проверяем, оставлял ли пользователь отзыв
        if Review.objects.filter(guide=guide, author=self.request.user).exists():
            raise serializers.ValidationError("Вы уже оставили отзыв на этот гайд.")

        # Сохраняем отзыв
        review = serializer.save(author=self.request.user, guide=guide, stars=stars)

        # Пересчитываем средний рейтинг руководства
        avg_rating = guide.reviews.aggregate(avg=Avg('stars'))['avg'] or 0
        guide.rating = int(round(avg_rating))
        guide.save(update_fields=['rating'])

        author_avg_rating = Guide.objects.filter(author=guide.author).aggregate(avg=Avg('rating'))['avg'] or 0
        profile = guide.author.profile
        profile.rating = int(round(author_avg_rating))
        profile.save(update_fields=['rating'])

    def create(self, request, *args, **kwargs):
        try:
            response = super().create(request, *args, **kwargs)
            # Добавляем обновлённый рейтинг в ответ
            guide_id = request.data.get("guide_id")
            guide = get_object_or_404(Guide, id=guide_id)
            response.data["guide_average_rating"] = guide.rating
            return response
        except serializers.ValidationError as e:
            return Response({"error": e.detail[0]}, status=status.HTTP_400_BAD_REQUEST)


class IsAuthorOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user


class GuideViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления руководствами (гайдами).
    
    list: Получить список всех руководств, отсортированных по рейтингу
    create: Создать новое руководство (требуется авторизация)
    retrieve: Получить руководство по ID
    update: Обновить руководство (только автор)
    destroy: Удалить руководство (только автор)
    """
    queryset = Guide.objects.all().order_by('-rating', '-created_at')
    serializer_class = GuideSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    @action(detail=False, methods=['get'], url_path='dao-guides')
    def get_guides_from_dao(self, request):
        """
        Метод, использующий DAO для получения списка руководств.
        Аналог @GetMapping("students").
        """
        guides = GuideDAO.get_all()
        serializer = GuideSerializer(guides, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='dto-guides')
    def get_dto_guides(self, request):
        dtos = GuideDAO.get_guides_dto()
        return Response([
            {
                "id": d.id,
                "title": d.title,
                "author": d.author_username,
                "rating": d.rating
            }
            for d in dtos
        ])

    @swagger_auto_schema(
        operation_description="Получить список всех руководств, отсортированных по рейтингу",
        tags=['Руководства']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Создать новое руководство",
        request_body=GuideSerializer,
        tags=['Руководства']
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Получить руководство по ID",
        tags=['Руководства']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Обновить руководство (только автор)",
        request_body=GuideSerializer,
        tags=['Руководства']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Частично обновить руководство (только автор)",
        request_body=GuideSerializer,
        tags=['Руководства']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Удалить руководство (только автор)",
        tags=['Руководства']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class GuideRateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Оценить руководство (гайд) от 1 до 5",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['rating'],
            properties={
                'rating': openapi.Schema(type=openapi.TYPE_INTEGER, description='Рейтинг от 1 до 5', minimum=1, maximum=5),
            }
        ),
        responses={
            200: openapi.Response(
                description="Рейтинг успешно обновлен",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'guide_average_rating': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'profile_average_rating': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                )
            ),
            400: "Некорректный рейтинг"
        },
        tags=['Руководства']
    )
    def post(self, request, guide_id):
        guide = get_object_or_404(Guide, id=guide_id)
        rating_value = int(request.data.get('rating', 0))

        if not 1 <= rating_value <= 5:
            return Response({'error': 'Рейтинг должен быть от 1 до 5'}, status=400)

        GuideRating.objects.update_or_create(
            guide=guide,
            reviewer=request.user,
            defaults={'rating': rating_value}
        )

        avg_guide_rating = guide.ratings.aggregate(avg=Avg('rating'))['avg'] or 0
        guide.rating = int(round(avg_guide_rating))
        guide.save(update_fields=['rating'])

        author_avg_rating = Guide.objects.filter(author=guide.author).aggregate(avg=Avg('rating'))['avg'] or 0
        profile = guide.author.profile
        profile.rating = int(round(author_avg_rating))
        profile.save(update_fields=['rating'])

        return Response({
            "guide_average_rating": guide.rating,
            "profile_average_rating": profile.rating
        })


@login_required
def create_announcement_view(request):
    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")
        tags_raw = request.POST.get("tags", "")
        tags_list = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]
        image = request.FILES.get("image")

        if title and description:
            Announcement.objects.create(
                title=title,
                description=description,
                author=request.user,
                tags=tags_list,
                image = image
            )
            return redirect("announcements_list")

    return render(request, "users/create_announcement.html")


class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления объявлениями.
    
    list: Получить список всех объявлений, отсортированных по дате создания
    create: Создать новое объявление (требуется авторизация)
    retrieve: Получить объявление по ID
    update: Обновить объявление
    destroy: Удалить объявление
    """
    queryset = Announcement.objects.all().order_by("-created_at")
    serializer_class = AnnouncementSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @swagger_auto_schema(
        operation_description="Получить список всех объявлений, отсортированных по дате создания",
        tags=['Объявления']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Создать новое объявление",
        request_body=AnnouncementSerializer,
        tags=['Объявления']
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Получить объявление по ID",
        tags=['Объявления']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Обновить объявление",
        request_body=AnnouncementSerializer,
        tags=['Объявления']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Частично обновить объявление",
        request_body=AnnouncementSerializer,
        tags=['Объявления']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Удалить объявление",
        tags=['Объявления']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class ReviewUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Обновить отзыв на руководство",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['text', 'stars'],
            properties={
                'text': openapi.Schema(type=openapi.TYPE_STRING, description='Текст отзыва'),
                'stars': openapi.Schema(type=openapi.TYPE_INTEGER, description='Рейтинг от 1 до 5', minimum=1, maximum=5),
            }
        ),
        responses={
            200: openapi.Response(
                description="Отзыв успешно обновлен",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'text': openapi.Schema(type=openapi.TYPE_STRING),
                        'stars': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'created_at': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME),
                        'guide_average_rating': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'profile_average_rating': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                )
            ),
            400: "Ошибка валидации",
            403: "Нет доступа"
        },
        tags=['Отзывы']
    )
    def put(self, request, pk):
        review = get_object_or_404(Review, pk=pk)

        if review.author != request.user:
            return Response({"error": "Нет доступа"}, status=403)

        stars = int(request.data.get("stars"))
        text = request.data.get("text", "").strip()

        if not text:
            return Response({"error": "Текст не может быть пустым"}, status=400)

        review.text = text
        review.stars = stars
        review.save()

        # Обновляем средний рейтинг гида
        avg_rating = review.guide.reviews.aggregate(avg=Avg('stars'))['avg'] or 0
        review.guide.rating = int(round(avg_rating))
        review.guide.save(update_fields=['rating'])

        # Обновляем рейтинг профиля автора
        author_avg_rating = Guide.objects.filter(author=review.guide.author).aggregate(avg=Avg('rating'))['avg'] or 0
        profile = review.guide.author.profile
        profile.rating = int(round(author_avg_rating))
        profile.save(update_fields=['rating'])

        return Response({
            "id": review.id,
            "text": review.text,
            "stars": review.stars,
            "created_at": review.created_at,
            "guide_average_rating": review.guide.rating,
            "profile_average_rating": profile.rating
        })


class ReviewDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Удалить отзыв на руководство",
        responses={
            200: openapi.Response(
                description="Отзыв успешно удален",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'guide_average_rating': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'profile_average_rating': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                )
            ),
            403: "Нет доступа",
            404: "Отзыв не найден"
        },
        tags=['Отзывы']
    )
    def delete(self, request, pk):
        # Находим отзыв
        review = get_object_or_404(Review, pk=pk)

        # Проверяем, что пользователь — автор
        if review.author != request.user:
            return Response({"error": "Нет доступа"}, status=403)

        guide = review.guide
        review.delete()

        # Обновляем средний рейтинг гида
        avg_rating = guide.reviews.aggregate(avg=Avg('stars'))['avg'] or 0
        guide.rating = int(round(avg_rating))
        guide.save(update_fields=['rating'])

        # Обновляем рейтинг профиля автора
        author_avg_rating = Guide.objects.filter(author=guide.author).aggregate(avg=Avg('rating'))['avg'] or 0
        profile = guide.author.profile
        profile.rating = int(round(author_avg_rating))
        profile.save(update_fields=['rating'])

        return Response({
            "message": "Отзыв удалён",
            "guide_average_rating": guide.rating,
            "profile_average_rating": profile.rating
        })


class ProfileCommentCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'comment'],
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='Username профиля'),
                'comment': openapi.Schema(type=openapi.TYPE_STRING, description='Текст комментария'),
            },
        ),
        responses={201: ProfileCommentSerializer}
    )
    def post(self, request):
        username = request.data.get("username", "").strip()
        comment_text = request.data.get("comment", "").strip()

        if not username:
            return Response({"error": "Не указан username профиля"}, status=status.HTTP_400_BAD_REQUEST)
        if not comment_text:
            return Response({"error": "Комментарий не может быть пустым"}, status=status.HTTP_400_BAD_REQUEST)

        profile = get_object_or_404(Profile, user__username=username)

        review, created = ProfileReview.objects.update_or_create(
            reviewer=request.user,
            profile=profile,
            defaults={"comment": comment_text}
        )

        serializer = ProfileCommentSerializer(review, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProfileCommentUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Редактирование комментария к профилю",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['text'],
            properties={
                'text': openapi.Schema(type=openapi.TYPE_STRING, description='Новый текст комментария'),
            },
        ),
        responses={
            200: ProfileCommentSerializer,
            403: "Нет прав на редактирование",
            404: "Комментарий не найден",
            400: "Комментарий не может быть пустым"
        }
    )
    def put(self, request, pk):
        comment = get_object_or_404(ProfileReview, id=pk)

        if comment.reviewer != request.user:
            return Response({"error": "Нет прав на редактирование"}, status=status.HTTP_403_FORBIDDEN)

        text = request.data.get("text", "").strip()
        if not text:
            return Response({"error": "Комментарий не может быть пустым"}, status=status.HTTP_400_BAD_REQUEST)

        comment.comment = text
        comment.is_edited = True
        comment.save()

        serializer = ProfileCommentSerializer(comment, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


# --- Удаление комментария ---
class ProfileCommentDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Удаление комментария к профилю",
        responses={
            204: "Комментарий удален",
            403: "Нет прав на удаление",
            404: "Комментарий не найден"
        }
    )
    def delete(self, request, pk):
        comment = get_object_or_404(ProfileReview, id=pk)

        if comment.reviewer != request.user:
            return Response({"error": "Нет прав на удаление"}, status=status.HTTP_403_FORBIDDEN)

        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AnnouncementCommentCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Создать комментарий к объявлению",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['announcement_id', 'content'],
            properties={
                'announcement_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID объявления'),
                'content': openapi.Schema(type=openapi.TYPE_STRING, description='Текст комментария'),
            }
        ),
        responses={
            201: openapi.Response(
                description="Комментарий успешно создан",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'content': openapi.Schema(type=openapi.TYPE_STRING),
                        'author': openapi.Schema(type=openapi.TYPE_STRING),
                        'created_at': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME),
                        'is_edited': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'announcement_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                )
            ),
            400: "Комментарий не может быть пустым"
        },
        tags=['Комментарии']
    )
    def post(self, request):
        announcement_id = request.data.get("announcement_id")
        content = request.data.get("content", "").strip()

        if not content:
            return Response({"error": "Комментарий не может быть пустым"}, status=status.HTTP_400_BAD_REQUEST)

        announcement = get_object_or_404(Announcement, id=announcement_id)

        # Создаем комментарий
        comment = AnnouncementComment.objects.create(
            announcement=announcement,
            author=request.user,
            content=content
        )

        # Получаем аватар автора
        author_avatar = None
        if hasattr(comment.author, 'profile') and comment.author.profile.avatar:
            author_avatar = comment.author.profile.avatar.url

        return Response({
            "id": comment.id,
            "content": comment.content,
            "author": comment.author.username,
            "author_avatar": author_avatar,
            "created_at": comment.created_at.strftime('%d.%m.%Y %H:%M'),
            "is_edited": comment.is_edited,
            "announcement_id": announcement.id
        }, status=status.HTTP_201_CREATED)


class AnnouncementCommentUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Обновить комментарий к объявлению",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['content'],
            properties={
                'content': openapi.Schema(type=openapi.TYPE_STRING, description='Новый текст комментария'),
            }
        ),
        responses={
            200: openapi.Response(
                description="Комментарий успешно обновлен",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'content': openapi.Schema(type=openapi.TYPE_STRING),
                        'is_edited': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'updated_at': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME),
                        'announcement_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                )
            ),
            400: "Комментарий не может быть пустым",
            403: "Нет доступа"
        },
        tags=['Комментарии']
    )
    def put(self, request, pk):
        comment = get_object_or_404(AnnouncementComment, pk=pk)

        # Проверяем, что пользователь - автор комментария
        if comment.author != request.user:
            return Response({"error": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

        content = request.data.get("content", "").strip()

        if not content:
            return Response({"error": "Комментарий не может быть пустым"}, status=status.HTTP_400_BAD_REQUEST)

        # Обновляем комментарий
        comment.content = content
        comment.is_edited = True
        comment.save()

        return Response({
            "id": comment.id,
            "content": comment.content,
            "is_edited": comment.is_edited,
            "updated_at": comment.updated_at,
            "announcement_id": comment.announcement.id
        })


class AnnouncementCommentDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Удалить комментарий к объявлению",
        responses={
            200: openapi.Response(
                description="Комментарий успешно удален",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'announcement_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                )
            ),
            403: "Нет доступа",
            404: "Комментарий не найден"
        },
        tags=['Комментарии']
    )
    def delete(self, request, pk):
        # Находим комментарий
        comment = get_object_or_404(AnnouncementComment, pk=pk)

        # Проверяем, что пользователь — автор
        if comment.author != request.user:
            return Response({"error": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

        announcement_id = comment.announcement.id
        comment.delete()

        return Response({
            "message": "Комментарий удалён",
            "announcement_id": announcement_id
        })


@swagger_auto_schema(
    method='get',
    operation_description="Получить популярные руководства и объявления для карусели на главной странице",
    responses={
        200: openapi.Response(
            description="Список популярных элементов",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'guides': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'title': openapi.Schema(type=openapi.TYPE_STRING),
                                'image': openapi.Schema(type=openapi.TYPE_STRING),
                                'author': openapi.Schema(type=openapi.TYPE_STRING),
                                'rating': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'url': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        )
                    ),
                    'announcements': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'title': openapi.Schema(type=openapi.TYPE_STRING),
                                'image': openapi.Schema(type=openapi.TYPE_STRING),
                                'author': openapi.Schema(type=openapi.TYPE_STRING),
                                'url': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        )
                    ),
                }
            )
        ),
        500: "Внутренняя ошибка сервера"
    },
    tags=['Главная страница']
)
@api_view(['GET'])
def popular_items(request):
    """Получить популярные руководства и объявления для карусели"""
    try:
        # Получаем популярные руководства (топ 5 по рейтингу)
        popular_guides = Guide.objects.order_by('-rating', '-created_at')[:5]
        guides_data = []
        for guide in popular_guides:
            request_obj = request
            image_url = None
            if guide.image:
                if request_obj:
                    image_url = request_obj.build_absolute_uri(guide.image.url)
                else:
                    image_url = guide.image.url
            
            guides_data.append({
                'id': guide.id,
                'title': guide.title,
                'image': image_url or None,
                'author': guide.author.username,
                'rating': guide.rating,
                'url': f'/guides/{guide.id}/',
                'type': 'guide'
            })
        
        # Получаем популярные объявления (последние 5)
        popular_announcements = Announcement.objects.order_by('-created_at')[:5]
        announcements_data = []
        for announcement in popular_announcements:
            request_obj = request
            image_url = None
            if announcement.image:
                if request_obj:
                    image_url = request_obj.build_absolute_uri(announcement.image.url)
                else:
                    image_url = announcement.image.url
            
            announcements_data.append({
                'id': announcement.id,
                'title': announcement.title,
                'image': image_url or None,
                'author': announcement.author.username,
                'url': f'/announcements/{announcement.id}/',
                'type': 'announcement'
            })
        
        # Объединяем и перемешиваем (можно отсортировать по дате создания)
        all_items = guides_data + announcements_data
        # Сортируем по дате создания (новые первыми)
        # Для этого нужно добавить created_at в данные
        return Response({
            'guides': guides_data,
            'announcements': announcements_data,
            'items': all_items[:6]  # Максимум 6 элементов для карусели
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='get',
    operation_description="Получить все элементы для поиска (профили, объявления, руководства)",
    responses={
        200: openapi.Response(
            description="Список всех элементов",
            schema=openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'title': openapi.Schema(type=openapi.TYPE_STRING),
                        'type': openapi.Schema(type=openapi.TYPE_STRING, enum=['профиль', 'объявление', 'руководство']),
                        'url': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            )
        ),
        500: "Внутренняя ошибка сервера"
    },
    tags=['Поиск']
)
@api_view(['GET'])
def search_all_items(request):
    """Получить все элементы для поиска из всех моделей"""
    try:
        results = []

        # Профили
        profiles = Profile.objects.select_related('user').all()
        for profile in profiles:
            results.append({
                'title': f"{profile.user.first_name} {profile.user.last_name}".strip() or profile.user.username,
                'type': 'профиль',
                'url': f'/users/{profile.user.username}/',
            })

        # Объявления
        announcements = Announcement.objects.select_related('author').all()
        for announcement in announcements:
            results.append({
                'title': announcement.title,
                'type': 'объявление',
                'url': f'/announcements/{announcement.id}/',
            })

        # Руководства
        guides = Guide.objects.select_related('author').all()
        for guide in guides:
            results.append({
                'title': guide.title,
                'type': 'руководство',
                'url': f'/guides/{guide.id}/',
            })

        return Response(results)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='get',
    operation_description="Поиск по всем моделям (профили, объявления, руководства)",
    manual_parameters=[
        openapi.Parameter(
            'q',
            openapi.IN_QUERY,
            description="Поисковый запрос",
            type=openapi.TYPE_STRING,
            required=True
        ),
    ],
    responses={
        200: openapi.Response(
            description="Результаты поиска",
            schema=openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'title': openapi.Schema(type=openapi.TYPE_STRING),
                        'type': openapi.Schema(type=openapi.TYPE_STRING, enum=['профиль', 'объявление', 'руководство']),
                        'url': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            )
        ),
        500: "Внутренняя ошибка сервера"
    },
    tags=['Поиск']
)
@api_view(['GET'])
def search_items(request):
    """Поиск по всем моделям"""
    query = request.GET.get('q', '').strip()

    if not query:
        return Response([])

    try:
        results = []

        # Поиск в профилях
        profiles = Profile.objects.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__username__icontains=query)
        ).select_related('user')[:10]

        for profile in profiles:
            full_name = f"{profile.user.first_name} {profile.user.last_name}".strip()
            results.append({
                'title': full_name or profile.user.username,
                'type': 'профиль',
                'url': f'/profiles/{profile.user.id}/',
            })

        # Поиск в объявлениях
        announcements = Announcement.objects.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        )[:10]

        for announcement in announcements:
            results.append({
                'title': announcement.title,
                'type': 'объявление',
                'url': f'/announcements/{announcement.id}/',
            })

        # Поиск в руководствах
        guides = Guide.objects.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query)
        )[:10]

        for guide in guides:
            results.append({
                'title': guide.title,
                'type': 'руководство',
                'url': f'/guides/{guide.id}/',
            })

        return Response(results[:20])

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='get',
    operation_description="Фильтрация объявлений по названию, тегам и дате",
    manual_parameters=[
        openapi.Parameter('search', openapi.IN_QUERY, description="Поиск по названию", type=openapi.TYPE_STRING),
        openapi.Parameter('tags', openapi.IN_QUERY, description="Теги через запятую", type=openapi.TYPE_STRING),
        openapi.Parameter('date_filter', openapi.IN_QUERY, description="today/week/month", type=openapi.TYPE_STRING),
    ],
    tags=['Объявления']
)
@api_view(['GET'])
def filter_announcements(request):
    try:
        queryset = Announcement.objects.all()

        search_query = request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(title__icontains=search_query)

        tags_query = request.GET.get('tags', '').strip()
        if tags_query:
            tags_list = [tag.strip().lower() for tag in tags_query.split(',') if tag.strip()]
            if tags_list:
                filtered_ids = []
                for announcement in queryset.iterator():
                    ann_tags = announcement.tags if isinstance(announcement.tags, list) else []
                    normalized = [str(t).lower().strip() for t in ann_tags if t]
                    if any(tag in normalized for tag in tags_list):
                        filtered_ids.append(announcement.id)
                queryset = queryset.filter(id__in=filtered_ids) if filtered_ids else queryset.none()

        date_filter = (request.GET.get('date_filter') or '').strip()
        if date_filter in ('today', 'week', 'month'):
            today = timezone.localdate()
            if date_filter == 'today':
                queryset = queryset.filter(created_at__date=today)
            elif date_filter == 'week':
                start_date = today - timedelta(days=7)
                queryset = queryset.filter(created_at__date__gte=start_date)
            elif date_filter == 'month':
                start_date = today - timedelta(days=30)
                queryset = queryset.filter(created_at__date__gte=start_date)

        queryset = queryset.order_by('-created_at')
        serializer = AnnouncementSerializer(queryset, many=True, context={'request': request})
        return Response({'count': queryset.count(), 'results': serializer.data})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='get',
    operation_description="Фильтрация руководств по названию, тегам и дате",
    manual_parameters=[
        openapi.Parameter('search', openapi.IN_QUERY, description="Поиск по названию", type=openapi.TYPE_STRING),
        openapi.Parameter('tags', openapi.IN_QUERY, description="Теги через запятую", type=openapi.TYPE_STRING),
        openapi.Parameter('date_filter', openapi.IN_QUERY, description="today/week/month", type=openapi.TYPE_STRING),
    ],
    tags=['Руководства']
)
@api_view(['GET'])
def filter_guides(request):
    try:
        queryset = Guide.objects.all()

        search_query = request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(title__icontains=search_query)

        tags_query = request.GET.get('tags', '').strip()
        if tags_query:
            tags_list = [tag.strip().lower() for tag in tags_query.split(',') if tag.strip()]
            if tags_list:
                filtered_ids = []
                for guide in queryset.iterator():
                    g_tags = guide.tags if isinstance(guide.tags, list) else []
                    normalized = [str(t).lower().strip() for t in g_tags if t]
                    if any(tag in normalized for tag in tags_list):
                        filtered_ids.append(guide.id)
                queryset = queryset.filter(id__in=filtered_ids) if filtered_ids else queryset.none()

        date_filter = (request.GET.get('date_filter') or '').strip()
        if date_filter in ('today', 'week', 'month'):
            today = timezone.localdate()
            if date_filter == 'today':
                queryset = queryset.filter(created_at__date=today)
            elif date_filter == 'week':
                start_date = today - timedelta(days=7)
                queryset = queryset.filter(created_at__date__gte=start_date)
            elif date_filter == 'month':
                start_date = today - timedelta(days=30)
                queryset = queryset.filter(created_at__date__gte=start_date)

        queryset = queryset.order_by('-rating', '-created_at')
        serializer = GuideSerializer(queryset, many=True, context={'request': request})
        return Response({'count': queryset.count(), 'results': serializer.data})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatContactsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Возвращает список собеседников с последним сообщением и количеством непрочитанных.
        """
        user = request.user
        messages = (
            ChatMessage.objects
            .filter(Q(sender=user) | Q(receiver=user))
            .select_related("sender", "receiver", "sender__profile", "receiver__profile")
            .order_by("-created_at")
        )

        contacts_map = {}
        for msg in messages:
            other = msg.receiver if msg.sender_id == user.id else msg.sender
            data = contacts_map.setdefault(
                other.id,
                {
                    "user_id": other.id,
                    "username": other.username,
                    "avatar": other.profile.avatar.url if hasattr(other, 'profile') and other.profile.avatar else None,
                    "last_message": "",
                    "last_message_at": None,
                    "unread_count": 0,
                },
            )

            if not data["last_message_at"] or msg.created_at > data["last_message_at"]:
                if msg.message.strip():
                    data["last_message"] = msg.message[:200]
                elif msg.image:
                    data["last_message"] = "Картинка"
                else:
                    data["last_message"] = "Без сообщений"
                data["last_message_at"] = msg.created_at

            if msg.receiver_id == user.id and not msg.is_read:
                data["unread_count"] += 1

        contacts = sorted(
            contacts_map.values(),
            key=lambda item: item["last_message_at"] or timezone.now(),
            reverse=True,
        )
        serializer = ChatContactSerializer(contacts, many=True)
        return Response(serializer.data)


class ChatMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        """
        Возвращает историю сообщений с конкретным пользователем и помечает входящие как прочитанные.
        """
        other_user = get_object_or_404(User, id=user_id)
        if other_user == request.user:
            return Response([])

        ChatMessage.objects.filter(
            sender=other_user,
            receiver=request.user,
            is_read=False
        ).update(is_read=True)

        messages = ChatMessage.objects.filter(
            (Q(sender=request.user, receiver=other_user) |
             Q(sender=other_user, receiver=request.user))
        ).order_by("created_at")

        serializer = ChatMessageSerializer(messages, many=True, context={"request": request})
        return Response(serializer.data)


class ChatSendMessageView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        Создаёт новое сообщение в чат.
        """
        receiver_id = request.data.get("receiver_id")
        text = (request.data.get("message") or "").strip()
        image = request.FILES.get("image")

        if not receiver_id:
            return Response({"error": "Не указан получатель"}, status=status.HTTP_400_BAD_REQUEST)
        if not text and not image:
            return Response({"error": "Сообщение не может быть пустым"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            receiver_id = int(receiver_id)
        except (TypeError, ValueError):
            return Response({"error": "Некорректный идентификатор получателя"}, status=status.HTTP_400_BAD_REQUEST)

        receiver = get_object_or_404(User, id=receiver_id)
        if receiver == request.user:
            return Response({"error": "Нельзя отправить сообщение самому себе"}, status=status.HTTP_400_BAD_REQUEST)

        message = ChatMessage.objects.create(
            sender=request.user,
            receiver=receiver,
            message=text,
            image=image,
        )

        serializer = ChatMessageSerializer(message, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method='get',
    operation_description="Получить историю активности пользователя",
    manual_parameters=[
        openapi.Parameter(
            'username',
            openapi.IN_PATH,
            description="Username пользователя",
            type=openapi.TYPE_STRING,
            required=True
        ),
    ],
    responses={
        200: openapi.Response(
            description="Список активностей пользователя",
            schema=openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'action': openapi.Schema(type=openapi.TYPE_STRING),
                        'action_display': openapi.Schema(type=openapi.TYPE_STRING),
                        'target_type': openapi.Schema(type=openapi.TYPE_STRING),
                        'target_type_display': openapi.Schema(type=openapi.TYPE_STRING),
                        'target_title': openapi.Schema(type=openapi.TYPE_STRING),
                        'created_at': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME),
                        'url': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            )
        ),
        404: "Пользователь не найден"
    },
    tags=['Активность']
)
@api_view(['GET'])
def user_activities(request, username):
    """Получить историю активности пользователя"""
    try:
        user_obj = get_object_or_404(User, username=username)
        activities = UserActivity.objects.filter(user=user_obj).order_by('-created_at')[:50]
        
        activities_data = []
        for activity in activities:
            # Определяем URL в зависимости от типа объекта
            url = None
            if activity.target_type == 'GUIDE' and activity.guide:
                url = f'/guides/{activity.guide.id}/'
            elif activity.target_type == 'ANNOUNCEMENT' and activity.announcement:
                url = f'/announcements/{activity.announcement.id}/'
            
            # Преобразуем время из UTC в локальное время
            local_time = timezone.localtime(activity.created_at)
            
            activities_data.append({
                'id': activity.id,
                'action': activity.action,
                'action_display': activity.get_action_display(),
                'target_type': activity.target_type,
                'target_type_display': activity.get_target_type_display(),
                'target_title': activity.target_title,
                'created_at': local_time.strftime('%d.%m.%Y %H:%M'),
                'time': local_time.strftime('%H:%M'),
                'url': url
            })
        
        return Response(activities_data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@swagger_auto_schema(
    operation_description="Сохранить выбранный язык пользователя в cookies",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'language': openapi.Schema(type=openapi.TYPE_STRING, description='Код языка (RU или EN)'),
        },
        required=['language']
    ),
    responses={
        200: openapi.Response(description="Язык успешно сохранен"),
        400: "Неверный формат данных"
    },
    tags=['Язык']
)
def set_language(request):
    """
    Сохраняет выбранный язык пользователя в cookies.
    Cookie будет храниться 1 год.
    """
    language = request.data.get('language', '').upper()
    
    if language not in ['RU', 'EN']:
        return Response(
            {'error': 'Неверный код языка. Используйте RU или EN'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    response = Response({'success': True, 'language': language})
    # Устанавливаем cookie на 1 год (365 дней)
    response.set_cookie(
        'lang',
        language,
        max_age=365 * 24 * 60 * 60,  # 1 год в секундах
        httponly=False,  # Доступен для JavaScript
        samesite='Lax',
        secure=False  # True для HTTPS
    )
    
    return response
