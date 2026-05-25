from django.shortcuts import get_object_or_404
from rest_framework import status, permissions, generics, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db.models import Avg, Count, Q
from .models import (Review, GuideReviewRating, ReviewReply, ReviewReplyRating, ProfileReview,
                     ProfileReviewRating, AnnouncementComment, AnnouncementCommentRating,
                     AnnouncementCommentReply, AnnouncementCommentReplyRating, Guide, Profile)
from .serializers import ReviewSerializer, ProfileCommentSerializer
from .utils import filter_text

class GuideReviewRatingView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, review_id):
        review = get_object_or_404(Review, id=review_id)
        if review.author == request.user: return Response({"error": "Нельзя оценивать свой отзыв"}, status=403)
        is_like = request.data.get('is_like')
        if is_like is None: return Response({"error": "Не указан тип оценки"}, status=400)
        rating = GuideReviewRating.objects.filter(review=review, user=request.user).first()
        if rating and rating.is_like == is_like: rating.delete(); user_action = None
        else: GuideReviewRating.objects.update_or_create(review=review, user=request.user, defaults={'is_like': is_like}); user_action = is_like
        return Response({'likes': review.ratings.filter(is_like=True).count(), 'dislikes': review.ratings.filter(is_like=False).count(), 'user_action': user_action})

class ReviewReplyCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, review_id):
        review = get_object_or_404(Review, id=review_id)
        text = request.data.get('text', '').strip()
        if not text: return Response({"error": "Текст пуст"}, status=400)
        if not text.startswith(f'@{review.author.username}'): text = f'@{review.author.username}, {text}'
        reply = ReviewReply.objects.create(review=review, author=request.user, text=text)
        author_avatar = reply.author.profile.avatar.url if hasattr(reply.author, 'profile') and reply.author.profile.avatar else None
        return Response({"id": reply.id, "text": reply.text, "author": reply.author.username, "author_avatar": author_avatar, "created_at": reply.created_at.strftime('%d.%m.%Y %H:%M'), "likes_count": 0, "dislikes_count": 0}, status=201)

class ReviewReplyRatingView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, reply_id):
        reply = get_object_or_404(ReviewReply, id=reply_id)
        if reply.author == request.user: return Response({"error": "Нельзя оценивать свой ответ"}, status=403)
        is_like = request.data.get('is_like')
        if is_like is None: return Response({"error": "Не указан тип оценки"}, status=400)
        rating = ReviewReplyRating.objects.filter(reply=reply, user=request.user).first()
        if rating and rating.is_like == is_like: rating.delete(); user_action = None
        else: ReviewReplyRating.objects.update_or_create(reply=reply, user=request.user, defaults={'is_like': is_like}); user_action = is_like
        return Response({'likes': reply.ratings.filter(is_like=True).count(), 'dislikes': reply.ratings.filter(is_like=False).count(), 'user_action': user_action})

class ReviewCreateView(generics.CreateAPIView):
    serializer_class = ReviewSerializer; permission_classes = [permissions.IsAuthenticated]
    def perform_create(self, serializer):
        guide_id = self.request.data.get("guide_id"); stars = int(self.request.data.get("stars", 0))
        guide = get_object_or_404(Guide, id=guide_id)
        if Review.objects.filter(guide=guide, author=self.request.user).exists(): raise serializers.ValidationError("Отзыв уже оставлен")
        serializer.save(author=self.request.user, guide=guide, stars=stars, text=filter_text(self.request.data.get('text', '')))
        guide.rating = int(round(guide.reviews.aggregate(avg=Avg('stars'))['avg'] or 0)); guide.save(update_fields=['rating'])
        profile = guide.author.profile; profile.rating = int(round(Guide.objects.filter(author=guide.author).aggregate(avg=Avg('rating'))['avg'] or 0)); profile.save(update_fields=['rating'])
    def create(self, request, *args, **kwargs):
        try: response = super().create(request, *args, **kwargs); response.data["guide_average_rating"] = get_object_or_404(Guide, id=request.data.get("guide_id")).rating; return response
        except serializers.ValidationError as e: return Response({"error": e.detail[0]}, status=400)

class ReviewUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def put(self, request, pk):
        review = get_object_or_404(Review, pk=pk)
        is_moderator = hasattr(request.user, 'profile') and request.user.profile.role in ['MODERATOR', 'ADMIN']
        if review.author != request.user and not is_moderator: return Response({"error": "Нет доступа"}, status=403)
        text = filter_text(request.data.get("text", "").strip()); stars = int(request.data.get("stars"))
        if not text: return Response({"error": "Текст пуст"}, status=400)
        review.text, review.stars = text, stars; review.save()
        guide = review.guide; guide.rating = int(round(guide.reviews.aggregate(avg=Avg('stars'))['avg'] or 0)); guide.save(update_fields=['rating'])
        profile = guide.author.profile; profile.rating = int(round(Guide.objects.filter(author=guide.author).aggregate(avg=Avg('rating'))['avg'] or 0)); profile.save(update_fields=['rating'])
        return Response({"id": review.id, "text": review.text, "stars": review.stars, "created_at": review.created_at, "guide_average_rating": guide.rating, "profile_average_rating": profile.rating})

class ReviewDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def delete(self, request, pk):
        review = get_object_or_404(Review, pk=pk)
        is_moderator = hasattr(request.user, 'profile') and request.user.profile.role in ['MODERATOR', 'ADMIN']
        if review.author != request.user and not is_moderator: return Response({"error": "Нет доступа"}, status=403)
        guide = review.guide; review.delete()
        guide.rating = int(round(guide.reviews.aggregate(avg=Avg('stars'))['avg'] or 0)); guide.save(update_fields=['rating'])
        profile = guide.author.profile; profile.rating = int(round(Guide.objects.filter(author=guide.author).aggregate(avg=Avg('rating'))['avg'] or 0)); profile.save(update_fields=['rating'])
        return Response({"message": "Отзыв удалён", "guide_average_rating": guide.rating, "profile_average_rating": profile.rating})

class ProfileReviewRatingView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, review_id):
        review = get_object_or_404(ProfileReview, id=review_id)
        if review.reviewer == request.user: return Response({"error": "Нельзя оценивать свой отзыв"}, status=403)
        is_like = request.data.get('is_like')
        if is_like is None: return Response({"error": "Не указан тип оценки"}, status=400)
        rating = ProfileReviewRating.objects.filter(review=review, user=request.user).first()
        if rating and rating.is_like == is_like: rating.delete(); user_action = None
        else: ProfileReviewRating.objects.update_or_create(review=review, user=request.user, defaults={'is_like': is_like}); user_action = is_like
        return Response({'likes': review.ratings.filter(is_like=True).count(), 'dislikes': review.ratings.filter(is_like=False).count(), 'user_action': user_action})

class ProfileCommentCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        username, comment_text = request.data.get("username", "").strip(), request.data.get("comment", "").strip()
        if not username: return Response({"error": "Не указан username"}, status=400)
        if not comment_text: return Response({"error": "Комментарий пуст"}, status=400)
        profile = get_object_or_404(Profile, user__username=username)
        if not profile.allow_reviews: return Response({"error": "Отзывы отключены"}, status=403)
        review, _ = ProfileReview.objects.update_or_create(reviewer=request.user, profile=profile, defaults={"comment": filter_text(comment_text)})
        return Response(ProfileCommentSerializer(review, context={'request': request}).data, status=201)

class ProfileCommentUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def put(self, request, pk):
        comment = get_object_or_404(ProfileReview, id=pk)
        if comment.reviewer != request.user: return Response({"error": "Нет прав"}, status=403)
        text = filter_text(request.data.get("text", "").strip())
        if not text: return Response({"error": "Текст пуст"}, status=400)
        comment.comment, comment.is_edited = text, True; comment.save()
        return Response(ProfileCommentSerializer(comment, context={'request': request}).data, status=200)

class ProfileCommentDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def delete(self, request, pk):
        comment = get_object_or_404(ProfileReview, id=pk)
        if comment.reviewer != request.user: return Response({"error": "Нет прав"}, status=403)
        comment.delete(); return Response(status=204)

class AnnouncementCommentRatingView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, comment_id):
        comment = get_object_or_404(AnnouncementComment, id=comment_id)
        if comment.author == request.user: return Response({"error": "Нельзя оценивать свой комментарий"}, status=403)
        is_like = request.data.get('is_like')
        if is_like is None: return Response({"error": "Не указан тип оценки"}, status=400)
        rating = AnnouncementCommentRating.objects.filter(comment=comment, user=request.user).first()
        if rating and rating.is_like == is_like: rating.delete(); user_action = None
        else: AnnouncementCommentRating.objects.update_or_create(comment=comment, user=request.user, defaults={'is_like': is_like}); user_action = is_like
        return Response({'likes': comment.ratings.filter(is_like=True).count(), 'dislikes': comment.ratings.filter(is_like=False).count(), 'user_action': user_action})

class AnnouncementCommentReplyCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, comment_id):
        comment = get_object_or_404(AnnouncementComment, id=comment_id); content = request.data.get('content', '').strip()
        if not content: return Response({"error": "Текст пуст"}, status=400)
        if not content.startswith(f'@{comment.author.username}'): content = f'@{comment.author.username}, {content}'
        reply = AnnouncementCommentReply.objects.create(comment=comment, author=request.user, content=content)
        author_avatar = reply.author.profile.avatar.url if hasattr(reply.author, 'profile') and reply.author.profile.avatar else None
        return Response({"id": reply.id, "content": reply.content, "author": reply.author.username, "author_avatar": author_avatar, "created_at": reply.created_at.strftime('%d.%m.%Y %H:%M'), "likes_count": 0, "dislikes_count": 0}, status=201)

class AnnouncementCommentReplyRatingView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, reply_id):
        reply = get_object_or_404(AnnouncementCommentReply, id=reply_id)
        if reply.author == request.user: return Response({"error": "Нельзя оценивать свой ответ"}, status=403)
        is_like = request.data.get('is_like')
        if is_like is None: return Response({"error": "Не указан тип оценки"}, status=400)
        rating = AnnouncementCommentReplyRating.objects.filter(reply=reply, user=request.user).first()
        if rating and rating.is_like == is_like: rating.delete(); user_action = None
        else: AnnouncementCommentReplyRating.objects.update_or_create(reply=reply, user=request.user, defaults={'is_like': is_like}); user_action = is_like
        return Response({'likes': reply.ratings.filter(is_like=True).count(), 'dislikes': reply.ratings.filter(is_like=False).count(), 'user_action': user_action})

class AnnouncementCommentCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        announcement_id, content = request.data.get("announcement_id"), request.data.get("content", "").strip()
        if not content: return Response({"error": "Комментарий пуст"}, status=400)
        announcement = get_object_or_404(Announcement, id=announcement_id)
        comment = AnnouncementComment.objects.create(announcement=announcement, author=request.user, content=filter_text(content))
        author_avatar = comment.author.profile.avatar.url if hasattr(comment.author, 'profile') and comment.author.profile.avatar else None
        return Response({"id": comment.id, "content": comment.content, "author": comment.author.username, "author_avatar": author_avatar, "created_at": comment.created_at.strftime('%d.%m.%Y %H:%M'), "is_edited": comment.is_edited, "announcement_id": announcement.id}, status=201)

class AnnouncementCommentUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def put(self, request, pk):
        comment = get_object_or_404(AnnouncementComment, pk=pk)
        is_moderator = hasattr(request.user, 'profile') and request.user.profile.role in ['MODERATOR', 'ADMIN']
        if comment.author != request.user and not is_moderator: return Response({"error": "Нет доступа"}, status=403)
        content = filter_text(request.data.get("content", "").strip())
        if not content: return Response({"error": "Комментарий пуст"}, status=400)
        comment.content, comment.is_edited = content, True; comment.save()
        return Response({"id": comment.id, "content": comment.content, "is_edited": comment.is_edited, "updated_at": comment.updated_at, "announcement_id": comment.announcement.id})

class AnnouncementCommentDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def delete(self, request, pk):
        comment = get_object_or_404(AnnouncementComment, pk=pk)
        is_moderator = hasattr(request.user, 'profile') and request.user.profile.role in ['MODERATOR', 'ADMIN']
        if comment.author != request.user and not is_moderator: return Response({"error": "Нет доступа"}, status=403)
        aid = comment.announcement.id; comment.delete()
        return Response({"message": "Комментарий удалён", "announcement_id": aid})