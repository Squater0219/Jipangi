from pathlib import Path

from django.db.models import Avg, Count, Max
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from config.exceptions import APIError

from .models import (
    PracticeSentence,
    PronunciationAnalysis,
    PronunciationError,
)
from .serializers import (
    AnalysisAcceptedSerializer,
    AnalysisCreateSerializer,
    AnalysisResultSerializer,
    AnalysisStatusSerializer,
    DIFFICULTY_TO_DB,
    RecommendationSerializer,
    RecordSerializer,
    SentenceDetailSerializer,
    SentenceListSerializer,
    StatisticsSummarySerializer,
)
from .services.audio import validate_audio
from .tasks import process_analysis


class SentenceListView(ListAPIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    serializer_class = SentenceListSerializer

    def get_queryset(self):
        queryset = PracticeSentence.objects.filter(is_active=True).select_related("category")
        category = self.request.query_params.get("category")
        difficulty = self.request.query_params.get("difficulty")

        if category:
            queryset = queryset.filter(category__code=category)
        if difficulty:
            if difficulty not in DIFFICULTY_TO_DB:
                raise APIError(
                    status_code=400,
                    code="INVALID_REQUEST",
                    message="난이도 값이 올바르지 않습니다.",
                    details={"difficulty": ["easy, normal, hard 중 하나여야 합니다."]},
                )
            queryset = queryset.filter(difficulty=DIFFICULTY_TO_DB[difficulty])
        return queryset


class SentenceDetailView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(responses={200: SentenceDetailSerializer})
    def get(self, request, sentence_id):
        sentence = (
            PracticeSentence.objects.filter(id=sentence_id, is_active=True)
            .select_related("category")
            .first()
        )
        if sentence is None:
            raise APIError(
                status_code=404,
                code="SENTENCE_NOT_FOUND",
                message="연습 문장을 찾을 수 없습니다.",
            )
        return Response(SentenceDetailSerializer(sentence).data)


class SentenceRecommendationView(APIView):
    @extend_schema(responses={200: RecommendationSerializer})
    def get(self, request):
        analyses = PronunciationAnalysis.objects.filter(
            user=request.user,
            status=PronunciationAnalysis.Status.COMPLETED,
            consent_to_store=True,
        )
        recent_analysis_ids = list(analyses.values_list("id", flat=True)[:30])
        category_error = (
            PronunciationError.objects.filter(
                analysis_id__in=recent_analysis_ids,
                analysis__sentence__category__isnull=False,
            )
            .values("analysis__sentence__category_id")
            .annotate(error_count=Count("id"))
            .order_by("-error_count", "analysis__sentence__category_id")
            .first()
        )

        analyzed_sentence_ids = analyses.values_list("sentence_id", flat=True)
        candidates = PracticeSentence.objects.filter(is_active=True).select_related("category")
        reason = "아직 학습 기록이 없어 쉬운 문장을 추천합니다."

        if category_error:
            category_id = category_error["analysis__sentence__category_id"]
            candidates = candidates.filter(category_id=category_id)
            category = candidates.first().category if candidates.exists() else None
            if category is not None:
                reason = f"최근 {category.name} 오류가 많아 해당 유형의 문장을 추천합니다."
        else:
            candidates = candidates.filter(difficulty=PracticeSentence.Difficulty.BEGINNER)

        sentence = candidates.exclude(id__in=analyzed_sentence_ids).order_by("?").first()
        if sentence is None:
            sentence = (
                PracticeSentence.objects.filter(
                    is_active=True,
                    difficulty=PracticeSentence.Difficulty.BEGINNER,
                )
                .select_related("category")
                .order_by("?")
                .first()
            )
            reason = "새로운 추천 조건에 맞는 문장이 없어 쉬운 문장을 추천합니다."

        if sentence is None:
            raise APIError(
                status_code=404,
                code="SENTENCE_NOT_FOUND",
                message="추천할 수 있는 연습 문장이 없습니다.",
            )

        response_data = SentenceListSerializer(sentence).data
        response_data["reason"] = reason
        return Response(response_data)


class AnalysisCreateView(APIView):
    @extend_schema(request=AnalysisCreateSerializer, responses={202: AnalysisAcceptedSerializer})
    def post(self, request):
        if "audio" not in request.FILES:
            raise APIError(
                status_code=400,
                code="AUDIO_FILE_REQUIRED",
                message="음성 파일이 필요합니다.",
            )

        serializer = AnalysisCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sentence = PracticeSentence.objects.filter(
            id=serializer.validated_data["sentence_id"],
            is_active=True,
        ).first()
        if sentence is None:
            raise APIError(
                status_code=404,
                code="SENTENCE_NOT_FOUND",
                message="연습 문장을 찾을 수 없습니다.",
            )
        if not sentence.cached_ipa:
            raise APIError(
                status_code=409,
                code="SENTENCE_IPA_NOT_READY",
                message="연습 문장의 목표 IPA가 준비되지 않았습니다.",
            )

        audio_path = validate_audio(serializer.validated_data["audio"])
        analysis = PronunciationAnalysis.objects.create(
            user=request.user,
            sentence=sentence,
            target_ipa=sentence.cached_ipa,
            status=PronunciationAnalysis.Status.PENDING,
            consent_to_store=serializer.validated_data["consent_to_store"],
        )
        try:
            process_analysis.delay(str(analysis.id), audio_path)
        except Exception as exc:
            Path(audio_path).unlink(missing_ok=True)
            analysis.delete()
            raise APIError(
                status_code=503,
                code="ANALYSIS_QUEUE_UNAVAILABLE",
                message="분석 작업을 등록할 수 없습니다.",
            ) from exc

        return Response(
            {"analysis_id": str(analysis.id), "status": "pending"},
            status=status.HTTP_202_ACCEPTED,
        )


class AnalysisStatusView(APIView):
    @extend_schema(responses={200: AnalysisStatusSerializer})
    def get(self, request, analysis_id):
        analysis = _user_analysis(request.user, analysis_id)
        return Response(
            {
                "analysis_id": str(analysis.id),
                "status": analysis.status,
            }
        )


class AnalysisResultView(APIView):
    @extend_schema(responses={200: AnalysisResultSerializer})
    def get(self, request, analysis_id):
        analysis = _user_analysis(request.user, analysis_id)
        if analysis.status in {
            PronunciationAnalysis.Status.PENDING,
            PronunciationAnalysis.Status.PROCESSING,
        }:
            raise APIError(
                status_code=409,
                code="ANALYSIS_IN_PROGRESS",
                message="발음 분석이 진행 중입니다.",
            )
        if analysis.status == PronunciationAnalysis.Status.FAILED:
            raise APIError(
                status_code=409,
                code="ANALYSIS_FAILED",
                message="발음 분석에 실패했습니다.",
            )

        analysis = (
            PronunciationAnalysis.objects.filter(id=analysis.id)
            .select_related("sentence", "feedback")
            .prefetch_related("errors")
            .get()
        )
        return Response(AnalysisResultSerializer(analysis).data)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, analysis_id):
        analysis = _user_analysis(request.user, analysis_id)
        if analysis.status in {
            PronunciationAnalysis.Status.PENDING,
            PronunciationAnalysis.Status.PROCESSING,
        }:
            raise APIError(
                status_code=409,
                code="ANALYSIS_IN_PROGRESS",
                message="진행 중인 분석은 삭제할 수 없습니다.",
            )
        analysis.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _user_analysis(user, analysis_id):
    analysis = PronunciationAnalysis.objects.filter(id=analysis_id, user=user).first()
    if analysis is None:
        raise APIError(
            status_code=404,
            code="ANALYSIS_NOT_FOUND",
            message="발음 분석 결과를 찾을 수 없습니다.",
        )
    if (
        not analysis.consent_to_store
        and analysis.expires_at is not None
        and analysis.expires_at <= timezone.now()
    ):
        analysis.delete()
        raise APIError(
            status_code=404,
            code="ANALYSIS_NOT_FOUND",
            message="발음 분석 결과를 찾을 수 없습니다.",
        )
    return analysis


class RecordListView(ListAPIView):
    serializer_class = RecordSerializer

    def get_queryset(self):
        queryset = (
            PronunciationAnalysis.objects.filter(
                user=self.request.user,
                status=PronunciationAnalysis.Status.COMPLETED,
                consent_to_store=True,
            )
            .select_related("sentence", "sentence__category")
            .annotate(error_count=Count("errors"))
            .order_by("-created_at")
        )
        category = self.request.query_params.get("category")
        difficulty = self.request.query_params.get("difficulty")
        if category:
            queryset = queryset.filter(sentence__category__code=category)
        if difficulty:
            if difficulty not in DIFFICULTY_TO_DB:
                raise APIError(
                    status_code=400,
                    code="INVALID_REQUEST",
                    message="난이도 값이 올바르지 않습니다.",
                    details={"difficulty": ["easy, normal, hard 중 하나여야 합니다."]},
                )
            queryset = queryset.filter(sentence__difficulty=DIFFICULTY_TO_DB[difficulty])
        return queryset


class StatisticsSummaryView(APIView):
    @extend_schema(responses={200: StatisticsSummarySerializer})
    def get(self, request):
        analyses = PronunciationAnalysis.objects.filter(
            user=request.user,
            status=PronunciationAnalysis.Status.COMPLETED,
            consent_to_store=True,
        )
        score_summary = analyses.aggregate(
            average_score=Avg("score"),
            best_score=Max("score"),
        )
        recent_scores = [
            {
                "analysis_id": str(row["id"]),
                "score": float(row["score"]),
                "created_at": row["created_at"],
            }
            for row in analyses.filter(score__isnull=False)
            .values("id", "score", "created_at")
            .order_by("-created_at")[:7]
        ]
        error_summary = [
            {
                "category": {
                    "code": row["analysis__sentence__category__code"],
                    "name": row["analysis__sentence__category__name"],
                },
                "count": row["count"],
            }
            for row in PronunciationError.objects.filter(
                analysis__in=analyses,
                analysis__sentence__category__isnull=False,
            )
            .values(
                "analysis__sentence__category__code",
                "analysis__sentence__category__name",
            )
            .annotate(count=Count("id"))
            .order_by("-count", "analysis__sentence__category__code")
        ]

        average_score = score_summary["average_score"]
        best_score = score_summary["best_score"]
        return Response(
            {
                "total_analyses": analyses.count(),
                "average_score": round(float(average_score), 1) if average_score else 0.0,
                "best_score": float(best_score) if best_score is not None else 0.0,
                "recent_scores": recent_scores,
                "error_summary": error_summary,
            }
        )
    RecordSerializer,
    AnalysisAcceptedSerializer,
    RecommendationSerializer,
