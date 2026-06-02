import random
import string
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db.models import Count, F, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from .models import Profile, UserActivity, Guide, Announcement, ProfileReview, ProfileReviewRating, \
    EmailVerificationCode, GuideRating, AnnouncementComment, GuideComment, Review, ChatMessage, FavoriteAnnouncement, \
    FavoriteGuide
from .serializers import RegisterSerializer, UserProfileSerializer, ReviewSerializer
from .utils import filter_text

# --- Страницы ---
def main_page(request): return render(request, "users/main.html")
def register_page(request): return render(request, "users/reg.html")
def reset_password_page(request): return render(request, "users/reset_password_page.html")
def change_password_page(request): return render(request, "users/change_password_page.html")
def login_page(request): return render(request, "users/log.html")

def blocked_page(request):
    if not request.user.is_authenticated: return redirect('login_page')
    if not (hasattr(request.user, 'profile') and request.user.profile.is_blocked): return redirect('main_page')
    return render(request, "users/blocked_page.html", {
        'reason': request.user.profile.blocked_reason or "Причина не указана", 'blocked_at': request.user.profile.blocked_at
    })

def profile_page(request, username):
    user_obj = get_object_or_404(User, username=username)
    profile = user_obj.profile
    guides = Guide.objects.filter(author=user_obj).order_by('-created_at')
    announcements = Announcement.objects.filter(author=user_obj).order_by('-created_at')
    activities = UserActivity.objects.filter(user=user_obj).order_by('-created_at')[:20]
    sort_by = request.GET.get('sort', 'new')
    reviews = ProfileReview.objects.filter(profile=profile).select_related('reviewer', 'reviewer__profile').annotate(
        likes_count=Count('ratings', filter=Q(ratings__is_like=True)), dislikes_count=Count('ratings', filter=Q(ratings__is_like=False))
    )
    if sort_by == 'Popular': reviews = reviews.annotate(net_rating=F('likes_count') - F('dislikes_count')).order_by('-net_rating', '-created_at')
    else: reviews = reviews.order_by('-created_at')
    user_liked, user_disliked = set(), set()
    if request.user.is_authenticated:
        for r in ProfileReviewRating.objects.filter(review__in=reviews, user=request.user):
            (user_liked if r.is_like else user_disliked).add(r.review_id)
    return render(request, "users/profile.html", {
        "username": username, "profile": profile, "guides": guides, "reviews": reviews,
        "announcements": announcements, "activities": activities, "user_liked": user_liked, "user_disliked": user_disliked, "sort_by": sort_by
    })

@login_required
def profile_edit(request):
    profile = request.user.profile
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        description = request.POST.get("description", "").strip()
        avatar = request.FILES.get("avatar")
        allow_reviews = request.POST.get('allow_reviews', 'true').lower() == 'true'
        profile.telegram = request.POST.get('social-telegram', '').strip() or None
        profile.github = request.POST.get('social-github', '').strip() or None
        profile.vk = request.POST.get('social-vk', '').strip() or None
        profile.youtube = request.POST.get('social-youtube', '').strip() or None
        website = request.POST.get('social-website', '').strip()
        profile.website = website if website else None
        banner_action = request.POST.get('banner_action', '')
        banner_value = request.POST.get('banner_value', '').strip()
        if banner_action == 'reset':
            if profile.banner_image: profile.banner_image.delete(save=False)
            profile.banner_image = profile.banner_style = None
        elif banner_action == 'image' and request.FILES.get('banner_image'):
            if profile.banner_image: profile.banner_image.delete(save=False)
            profile.banner_image = request.FILES['banner_image']; profile.banner_style = None
        elif banner_action in ['gradient', 'color'] and banner_value:
            profile.banner_style = banner_value
            if profile.banner_image: profile.banner_image.delete(save=False)
            profile.banner_image = None
        if username and username != request.user.username:
            if User.objects.filter(username=username).exclude(id=request.user.id).exists():
                return render(request, "users/profile_edit.html", {"profile": profile, "user": request.user})
            request.user.username = username; request.user.save()
        profile.bio, profile.allow_reviews = description, allow_reviews
        if avatar: profile.avatar = avatar
        profile.save()
        return redirect(f"{request.path}?updated=1")
    socials = {'telegram': profile.telegram or '', 'github': profile.github or '', 'vk': profile.vk or '', 'youtube': profile.youtube or '', 'website': profile.website or ''}
    banner_data = {}
    if profile.banner_image: banner_data = {'type': 'image', 'value': profile.banner_image.url}
    elif profile.banner_style: banner_data = {'type': 'gradient' if 'gradient' in profile.banner_style.lower() else 'color', 'value': profile.banner_style}
    return render(request, "users/profile_edit.html", {"profile": profile, "user": request.user, "socials": socials, "banner_data": banner_data})

def logout_view(request): logout(request); return redirect("main_page")

def profile_guides_api(username):
    user_obj = get_object_or_404(User, username=username)
    guides = Guide.objects.filter(author=user_obj).order_by('-created_at')
    return JsonResponse({"guides": [{"id": g.id, "title": g.title, "image": g.image.url if g.image else None, "created_at": g.created_at} for g in guides]})

# --- API Auth ---
class RegisterView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data.get('email')
            if not email: return Response({"error": "Email обязателен"}, status=400)
            if User.objects.filter(email=email).exists(): return Response({"error": "Email уже существует"}, status=400)
            user = serializer.save(); user.is_active = False; user.save()
            code = ''.join(random.choices(string.digits, k=6))
            expires_at = timezone.now() + timedelta(minutes=15)
            EmailVerificationCode.objects.create(user=user, code=code, email=email, expires_at=expires_at)
            send_mail('Подтверждение регистрации', f'Код: {code}', None, [email], fail_silently=False)
            return Response({"message": "Код отправлен", "id": user.id, "email": email}, status=201)
        return Response(serializer.errors, status=400)

class LoginView(APIView):
    permission_classes = [AllowAny]; authentication_classes = []
    def post(self, request):
        username, password = request.data.get("username"), request.data.get("password")
        if not username or not password: return Response({"error": "Введите логин и пароль"}, status=400)
        user = authenticate(request, username=username, password=password)
        if user is None: return Response({"error": "Неверные данные"}, status=401)
        if not user.is_active: return Response({"error": "Email не подтвержден"}, status=401)
        login(request, user)
        if hasattr(user, 'profile') and user.profile.is_blocked:
            return Response({"error": "Аккаунт заблокирован", "reason": user.profile.blocked_reason or "Причина не указана"}, status=403)
        refresh = RefreshToken.for_user(user)
        return Response({"access": str(refresh.access_token), "refresh": str(refresh), "username": user.username, "email": user.email}, status=200)

class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        email, code = request.data.get('email'), request.data.get('code')
        if not email or not code: return Response({"error": "Укажите email и код"}, status=400)
        try: user = User.objects.get(email=email)
        except User.DoesNotExist: return Response({"error": "Пользователь не найден"}, status=404)
        verification = EmailVerificationCode.objects.filter(user=user, email=email, code=code, is_used=False).order_by('-created_at').first()
        if not verification: return Response({"error": "Неверный код"}, status=400)
        if verification.is_expired(): return Response({"error": "Код истек"}, status=400)
        verification.is_used = True; verification.save(); user.is_active = True; user.save()
        return Response({"message": "Email подтвержден", "username": user.username}, status=200)

class ResendVerificationCodeView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        email = request.data.get('email')
        if not email: return Response({"error": "Укажите email"}, status=400)
        try: user = User.objects.get(email=email)
        except User.DoesNotExist: return Response({"error": "Пользователь не найден"}, status=400)
        if user.is_active: return Response({"error": "Email уже подтвержден"}, status=400)
        code = ''.join(random.choices(string.digits, k=6))
        expires_at = timezone.now() + timedelta(minutes=15)
        EmailVerificationCode.objects.create(user=user, code=code, email=email, expires_at=expires_at)
        send_mail('Подтверждение регистрации', f'Код: {code}', None, [email], fail_silently=False)
        return Response({"message": "Код отправлен повторно"}, status=200)

class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request): return Response({"id": request.user.id, "username": request.user.username, "email": request.user.email, "is_active": request.user.is_active, "date_joined": request.user.date_joined})

class UserProfileDetailView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    def get_object(self): return get_object_or_404(Profile, user__username=self.kwargs.get("username"))

class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        email = request.data.get('email')
        if not email: return Response({"error": "Укажите email"}, status=400)
        try: user = User.objects.get(email=email)
        except User.DoesNotExist: return Response({"error": "Пользователь не найден"}, status=404)
        code = ''.join(random.choices(string.digits, k=6))
        expires_at = timezone.now() + timedelta(minutes=15)
        EmailVerificationCode.objects.create(user=user, code=code, email=email, expires_at=expires_at)
        print(f"Код восстановления пароля для {email}: {code}")
        return Response({"message": "Код восстановления отправлен"}, status=200)

class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        email, code, new_password = request.data.get('email'), request.data.get('code'), request.data.get('new_password')
        if not all([email, code, new_password]): return Response({"error": "Заполните все поля"}, status=400)
        if len(new_password) < 8: return Response({"error": "Пароль минимум 8 символов"}, status=400)
        try: user = User.objects.get(email=email)
        except User.DoesNotExist: return Response({"error": "Пользователь не найден"}, status=404)
        verification = EmailVerificationCode.objects.filter(user=user, email=email, code=code, is_used=False).order_by('-created_at').first()
        if not verification or verification.is_expired(): return Response({"error": "Неверный или истекший код"}, status=400)
        verification.is_used = True; verification.save(); user.password = make_password(new_password); user.save()
        return Response({"message": "Пароль изменен"}, status=200)

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        old_password, new_password = request.data.get('old_password'), request.data.get('new_password')
        if not all([old_password, new_password]): return Response({"error": "Заполните все поля"}, status=400)
        if not request.user.check_password(old_password): return Response({"error": "Неверный старый пароль"}, status=400)
        if len(new_password) < 8: return Response({"error": "Новый пароль минимум 8 символов"}, status=400)
        request.user.set_password(new_password); request.user.save(); update_session_auth_hash(request, request.user)
        return Response({"message": "Пароль изменен"}, status=200)

@login_required
def delete_account(request):
    user = request.user
    # Удаление связанных данных
    AnnouncementComment.objects.filter(author=user).delete()
    GuideComment.objects.filter(author=user).delete()
    Review.objects.filter(author=user).delete()
    GuideRating.objects.filter(reviewer=user).delete()
    ProfileReview.objects.filter(reviewer=user).delete()
    ProfileReview.objects.filter(profile=user.profile).delete()
    ChatMessage.objects.filter(sender=user).delete()
    ChatMessage.objects.filter(receiver=user).delete()
    EmailVerificationCode.objects.filter(user=user).delete()
    UserActivity.objects.filter(user=user).delete()
    FavoriteGuide.objects.filter(user=user).delete()
    FavoriteAnnouncement.objects.filter(user=user).delete()
    Announcement.objects.filter(author=user).delete()
    Guide.objects.filter(author=user).delete()
    Profile.objects.filter(user=user).delete()
    user.delete(); logout(request)
    return JsonResponse({'success': True, 'message': 'Аккаунт удалён'})