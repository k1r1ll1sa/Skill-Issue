import json
from unittest.mock import patch
from django.test import override_settings
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from django.urls import reverse
from .models import (
    Profile, EmailVerificationCode, UserActivity, Guide, Announcement, Review, AnnouncementComment
)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class BaseAPITest(APITestCase):
    """Базовый класс с настройками аутентификации и общими данными"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='TestPass123!')
        self.profile = Profile.objects.create(user=self.user)
        self.refresh = RefreshToken.for_user(self.user)
        self.access_token = str(self.refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        self.other_user = User.objects.create_user(username='otheruser', email='other@example.com',
                                                   password='OtherPass123!')
        Profile.objects.create(user=self.other_user)

        self.guide = Guide.objects.create(author=self.user, title='Test Guide', content='Content')
        self.announcement = Announcement.objects.create(author=self.user, title='Test Ann', description='Desc')


# ================= AUTH & ACCOUNT =================
class AuthAPITests(BaseAPITest):
    @patch('django.core.mail.send_mail')
    def test_register_success(self, mock_mail):
        payload = {'username': 'newuser', 'email': 'new@test.com', 'password': 'NewPass123!'}
        res = self.client.post('/api/register/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertTrue(User.objects.filter(username='newuser').exists())
        self.assertTrue(Profile.objects.filter(user__username='newuser').exists())

    def test_login_success(self):
        self.user.is_active = True
        self.user.save()
        payload = {'username': 'testuser', 'password': 'TestPass123!'}
        res = self.client.post('/api/login/', payload, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('access', res.data)

    def test_login_blocked_user(self):
        self.user.is_active = True
        self.user.save()
        self.profile.is_blocked = True
        self.profile.blocked_reason = "Нарушение правил"
        self.profile.save()
        payload = {'username': 'testuser', 'password': 'TestPass123!'}
        res = self.client.post('/api/login/', payload, format='json')
        self.assertEqual(res.status_code, 403)
        self.assertIn('заблокирован', res.data['error'].lower())

    def test_current_user(self):
        res = self.client.get('/api/me/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['username'], 'testuser')

    def test_logout_view(self):
        self.client.login(username='testuser', password='TestPass123!')
        res = self.client.get('/logout/')
        self.assertRedirects(res, reverse('main_page'))

    @patch('django.core.mail.send_mail')
    def test_password_reset_flow(self, mock_mail):
        res = self.client.post('/api/auth/password-reset/request/', {'email': 'test@example.com'}, format='json')
        self.assertEqual(res.status_code, 200)
        code = EmailVerificationCode.objects.filter(user=self.user, is_used=False).first().code

        # Confirm
        res = self.client.post('/api/auth/password-reset/confirm/', {
            'email': 'test@example.com', 'code': code, 'new_password': 'NewSecurePass1!'
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewSecurePass1!'))

    def test_blocked_page_redirects(self):
        res = self.client.get('/blocked/')
        self.assertRedirects(res, reverse('login_page'))


# ================= PROFILE & ACTIVITIES =================
class ProfileAPITests(BaseAPITest):
    def test_profile_page(self):
        res = self.client.get(f'/users/{self.user.username}/')
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'users/profile.html')

    def test_profile_comments_crud(self):
        # Create
        res = self.client.post('/api/profile/comments/create/', {
            'username': self.other_user.username, 'comment': 'Nice profile!'
        }, format='json')
        self.assertEqual(res.status_code, 201)
        pk = res.data['id']

        # Update
        res = self.client.put(f'/api/profile/comments/{pk}/update/', {'text': 'Updated comment'}, format='json')
        self.assertEqual(res.status_code, 200)

        # Delete
        res = self.client.delete(f'/api/profile/comments/{pk}/delete/')
        self.assertEqual(res.status_code, 204)

    def test_user_activities(self):
        UserActivity.objects.create(user=self.user, action='CREATE', target_type='GUIDE', target_title='Test')
        res = self.client.get(f'/api/users/{self.user.username}/activities/')
        self.assertEqual(res.status_code, 200)


# ================= GUIDES =================
class GuideAPITests(BaseAPITest):

    def test_guide_list(self):
        """Тест получения списка руководств"""
        res = self.client.get('/api/guides/')
        self.assertEqual(res.status_code, 200)

    def test_guide_create_authenticated(self):
        """Тест создания руководства авторизованным пользователем"""
        payload = {'title': 'New Guide', 'content': 'Content here', 'tags': ['test']}
        res = self.client.post('/api/guides/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['title'], 'New Guide')
        self.assertEqual(res.data['author_name'], self.user.username)
        self.assertTrue(Guide.objects.filter(id=res.data['id']).exists())

    def test_guide_create_unauthenticated(self):
        """Тест создания руководства неавторизованным пользователем"""
        client = APIClient()
        payload = {'title': 'New Guide', 'content': 'Content'}
        res = client.post('/api/guides/', payload, format='json')

        self.assertEqual(res.status_code, 401)

    def test_guide_retrieve(self):
        """Тест получения конкретного руководства"""
        res = self.client.get(f'/api/guides/{self.guide.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['id'], self.guide.id)
        self.assertEqual(res.data['title'], self.guide.title)

    def test_guide_update_by_author(self):
        """Тест обновления руководства автором"""
        payload = {'title': 'Updated Title', 'content': 'Updated content'}
        res = self.client.put(f'/api/guides/{self.guide.id}/', payload, format='json')
        self.assertEqual(res.status_code, 200)
        self.guide.refresh_from_db()
        self.assertEqual(self.guide.title, 'Updated Title')

    def test_guide_update_by_other_user(self):
        """Тест обновления руководства другим пользователем"""
        other_client = APIClient()
        other_refresh = RefreshToken.for_user(self.other_user)
        other_client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(other_refresh.access_token)}')

        payload = {'title': 'Hacked Title', 'content': 'Hacked'}
        res = other_client.put(f'/api/guides/{self.guide.id}/', payload, format='json')
        self.assertEqual(res.status_code, 403)

    def test_guide_delete_by_author(self):
        """Тест удаления руководства автором"""
        res = self.client.delete(f'/api/guides/{self.guide.id}/')
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Guide.objects.filter(id=self.guide.id).exists())

    def test_guide_dao_action(self):
        """Тест экшна get_guides_from_dao"""
        res = self.client.get('/api/guides/dao-guides/')
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.data, list)
        if res.data:
            self.assertIn('title', res.data[0])

    def test_guide_dto_action(self):
        """Тест экшна get_dto_guides"""
        res = self.client.get('/api/guides/dto-guides/')
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.data, list)
        if res.data:
            self.assertIn('author', res.data[0])
            self.assertIn('rating', res.data[0])

    def test_rate_guide_valid(self):
        """Тест оценки руководства валидным рейтингом"""
        res = self.client.post(f'/api/guides/{self.guide.id}/rate/', {'rating': 4}, format='json')
        self.assertEqual(res.status_code, 200)
        self.guide.refresh_from_db()
        self.assertEqual(self.guide.rating, 4)
        self.assertIn('guide_average_rating', res.data)
        self.assertIn('profile_average_rating', res.data)

    def test_rate_guide_invalid(self):
        """Тест оценки руководства невалидным рейтингом"""
        for invalid_rating in [0, 6, 10, -1]:
            res = self.client.post(f'/api/guides/{self.guide.id}/rate/', {'rating': invalid_rating}, format='json')
            self.assertEqual(res.status_code, 400)
            self.assertIn('error', res.data)

    def test_rate_guide_unauthenticated(self):
        """Тест оценки руководства неавторизованным пользователем"""
        client = APIClient()
        res = client.post(f'/api/guides/{self.guide.id}/rate/', {'rating': 5}, format='json')
        self.assertEqual(res.status_code, 401)

    def test_filter_guides_by_search(self):
        """Тест фильтрации руководств по поисковому запросу"""
        Guide.objects.create(author=self.user, title='Python Guide', content='Learn Python', tags=['python'])
        Guide.objects.create(author=self.user, title='Java Guide', content='Learn Java', tags=['java'])

        res = self.client.get('/api/guides/filter/?search=Python')
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(res.data['count'], 1)
        titles = [r['title'] for r in res.data['results']]
        self.assertIn('Python Guide', titles)

    def test_filter_guides_by_tags(self):
        """Тест фильтрации руководств по тегам"""
        Guide.objects.create(author=self.user, title='Django Guide', tags=['django', 'python'])
        Guide.objects.create(author=self.user, title='Flask Guide', tags=['flask', 'python'])

        res = self.client.get('/api/guides/filter/?tags=django')
        self.assertEqual(res.status_code, 200)
        titles = [r['title'] for r in res.data['results']]
        self.assertIn('Django Guide', titles)
        self.assertNotIn('Flask Guide', titles)

    def test_filter_guides_by_date(self):
        """Тест фильтрации руководств по дате"""
        from datetime import timedelta
        old_guide = Guide.objects.create(
            author=self.user,
            title='Old Guide',
            created_at=timezone.now() - timedelta(days=10)
        )
        new_guide = Guide.objects.create(
            author=self.user,
            title='New Guide',
            created_at=timezone.now()
        )

        res = self.client.get('/api/guides/filter/?date_filter=5')
        self.assertEqual(res.status_code, 200)
        titles = [r['title'] for r in res.data['results']]
        self.assertIn('New Guide', titles)
        self.assertNotIn('Old Guide', titles)

    def test_filter_guides_combined(self):
        """Тест комбинированной фильтрации"""
        Guide.objects.create(
            author=self.user,
            title='Advanced Python',
            content='Deep dive',
            tags=['python', 'advanced']
        )

        res = self.client.get('/api/guides/filter/?search=Python&tags=advanced')
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(res.data['count'], 1)


# ================= ANNOUNCEMENTS =================
class AnnouncementAPITests(BaseAPITest):
    def test_announcement_crud(self):
        # List
        res = self.client.get('/api/announcements/')
        self.assertEqual(res.status_code, 200)

        # Create
        payload = {
            'title': 'New Ann',
            'description': 'Desc',
            'tags': json.dumps(['test'])
        }
        res = self.client.post('/api/announcements/', payload, format='multipart')
        self.assertEqual(res.status_code, 201, f"Ошибка валидации: {res.data}")  # ← полезно для отладки
        pk = res.data['id']
        self.assertEqual(res.data['title'], 'New Ann')
        self.assertEqual(res.data['author'], self.user.username)

        # Retrieve
        res = self.client.get(f'/api/announcements/{pk}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['id'], pk)

        # Update
        res = self.client.put(f'/api/announcements/{pk}/', {
            'title': 'Updated',
            'description': 'Desc',
            'tags': json.dumps(['test'])
        }, format='multipart')
        self.assertEqual(res.status_code, 200, f"Ошибка валидации: {res.data}")
        self.assertEqual(res.data['title'], 'Updated')

        # Destroy
        res = self.client.delete(f'/api/announcements/{pk}/')
        self.assertEqual(res.status_code, 204)

    def test_announcement_comments(self):
        # Create
        res = self.client.post('/api/announcements/comments/create/', {
            'announcement_id': self.announcement.id, 'content': 'Interesting!'
        }, format='json')
        self.assertEqual(res.status_code, 201)
        pk = res.data['id']
        self.assertEqual(res.data['content'], 'Interesting!')
        self.assertEqual(res.data['announcement_id'], self.announcement.id)

        # Update
        res = self.client.put(f'/api/announcements/comments/{pk}/update/', {'content': 'Edited'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['content'], 'Edited')
        self.assertTrue(res.data['is_edited'])

        # Delete - возвращает 200 с сообщением, а не 204
        res = self.client.delete(f'/api/announcements/comments/{pk}/delete/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('message', res.data)

    def test_announcement_comment_rating(self):
        comment = AnnouncementComment.objects.create(
            announcement=self.announcement,
            author=self.other_user,
            content='Hi'
        )
        # Like
        res = self.client.post(f'/api/announcements/comments/{comment.id}/rate/', {'is_like': True}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('likes', res.data)
        self.assertIn('dislikes', res.data)
        self.assertEqual(res.data['likes'], 1)
        self.assertEqual(res.data['dislikes'], 0)


# ================= REVIEWS & REPLIES =================
class ReviewAPITests(BaseAPITest):
    def test_review_create_prevents_duplicate(self):
        Review.objects.create(guide=self.guide, author=self.user, text='First', stars=5)
        res = self.client.post('/api/reviews/create/', {
            'guide_id': self.guide.id, 'text': 'Second', 'stars': 4
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_review_update_delete(self):
        review = Review.objects.create(guide=self.guide, author=self.user, text='Good', stars=5)
        res = self.client.put(f'/api/reviews/{review.id}/update/', {'text': 'Great', 'stars': 4}, format='json')
        self.assertEqual(res.status_code, 200)

        res = self.client.delete(f'/api/reviews/{review.id}/delete/')
        self.assertEqual(res.status_code, 200)

    def test_review_rating_and_replies(self):
        review = Review.objects.create(guide=self.guide, author=self.other_user, text='Nice', stars=5)

        # Rate
        res = self.client.post(f'/api/reviews/{review.id}/rate/', {'is_like': True}, format='json')
        self.assertEqual(res.status_code, 200)

        # Reply
        res = self.client.post(f'/api/reviews/{review.id}/reply/', {'text': 'Thanks!'}, format='json')
        self.assertEqual(res.status_code, 201)