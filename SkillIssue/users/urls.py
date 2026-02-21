from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView
from . import views
from django.conf import settings
from django.conf.urls.static import static

from .views import (GuideRateAPIView, ReviewCreateView, create_announcement_view,
    ReviewUpdateView, ReviewDeleteView, AnnouncementListView, GuideListView, ProfileCommentCreateView,
                    ProfileCommentUpdateView, ProfileCommentDeleteView)

router = DefaultRouter()
router.register(r'guides', views.GuideViewSet, basename='guides')
router.register(r'announcements', views.AnnouncementViewSet, basename='announcements')

urlpatterns = [
    # --- API endpoints ---
    path('api/register/', views.RegisterView.as_view(), name='api_register'),
    path("api/login/", views.LoginView.as_view(), name="login"),
    path("api/verify-email/", views.VerifyEmailView.as_view(), name="verify_email"),
    path("api/resend-code/", views.ResendVerificationCodeView.as_view(), name="resend_code"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/me/", views.CurrentUserView.as_view(), name="current_user"),
    path("api/chat/contacts/", views.ChatContactsView.as_view(), name="chat_contacts"),
    path("api/chat/<int:user_id>/messages/", views.ChatMessagesView.as_view(), name="chat_messages"),
    path("api/chat/send/", views.ChatSendMessageView.as_view(), name="chat_send_message"),
    path("logout/", views.logout_view, name="logout_page"),

    # --- Основные страницы ---
    path("", views.main_page, name="main_page"),
    path("register-page/", views.register_page, name="register_page"),
    path("login-page/", views.login_page, name="login_page"),
    path("favorites/", views.favorites_page, name="favorites_page"),

    # --- Профили ---
    path("users/edit/", views.profile_edit, name='profile_edit'),
    path("users/<str:username>/", views.profile_page, name="profile_page"),

    # --- API для профилей ---
    path("api/profile/<str:username>/", views.UserProfileDetailView.as_view(), name="profile-detail"),
    path("api/profile/reviews/create/", views.ReviewCreateView.as_view(), name="review-create"),
    path('api/profile/<str:username>/guides/', views.profile_guides_api, name='profile_guides_api'),
    path('api/profile/comments/create/', ProfileCommentCreateView.as_view(), name='profile-comment-create'),
    path('api/profile/comments/<int:pk>/update/', ProfileCommentUpdateView.as_view(), name='profile-comment-update'),
    path('api/profile/comments/<int:pk>/delete/', ProfileCommentDeleteView.as_view(), name='profile-comment-delete'),

    # --- API для рейтинга руководств ---
    path('api/guides/<int:guide_id>/rate/', GuideRateAPIView.as_view(), name='guide-rate'),
    path('api/reviews/create/', ReviewCreateView.as_view(), name='review-create'),
    path('api/reviews/<int:pk>/update/', ReviewUpdateView.as_view(), name='review-update'),
    path('api/reviews/<int:pk>/delete/', ReviewDeleteView.as_view(), name='review-delete'),


    # --- Руководства ---
    path('guides/', GuideListView.as_view(), name='guides_list'),
    path('create_guide/', views.create_guide, name='create_guide'),
    path("guides/<int:pk>/", views.guide_detail, name="guide_detail"),


    # --- API для объявлений ---
    path('api/announcements/comments/create/', views.AnnouncementCommentCreateView.as_view(),
         name='create_announcement_comment'),
    path('api/announcements/comments/<int:pk>/update/', views.AnnouncementCommentUpdateView.as_view(),
         name='update_announcement_comment'),
    path('api/announcements/comments/<int:pk>/delete/', views.AnnouncementCommentDeleteView.as_view(),
         name='delete_announcement_comment'),



    # --- Объявления ---
    path('create/', create_announcement_view, name='create'),
    path("announcements/", AnnouncementListView.as_view(), name="announcements_list"),
    path('announcements/<int:announcement_id>/', views.announcement_detail, name='announcement_detail'),
    path('announcements/<int:announcement_id>/edit/', views.edit_announcement, name='edit_announcement'),
    path('announcements/<int:announcement_id>/update/', views.update_announcement, name='update_announcement'),

    # --- API для фильтрации ---
    path('api/announcements/filter/', views.filter_announcements, name='filter_announcements'),
    path('api/guides/filter/', views.filter_guides, name='filter_guides'),

    # --- DRF Router ---
    path('api/', include(router.urls)),

    path('api/search/all/', views.search_all_items, name='search_all'),
    path('api/search/', views.search_items, name='search'),
    path('api/popular-items/', views.popular_items, name='popular_items'),
    path('api/users/<str:username>/activities/', views.user_activities, name='user_activities'),
    path('api/set-language/', views.set_language, name='set_language'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
