from rest_framework import serializers
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field

from .models import (
    CorrectionFeedback,
    PracticeSentence,
    PronunciationAnalysis,
    PronunciationCategory,
    PronunciationError,
)


DIFFICULTY_TO_API = {
    PracticeSentence.Difficulty.BEGINNER: "easy",
    PracticeSentence.Difficulty.INTERMEDIATE: "normal",
    PracticeSentence.Difficulty.ADVANCED: "hard",
}
DIFFICULTY_TO_DB = {value: key for key, value in DIFFICULTY_TO_API.items()}


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PronunciationCategory
        fields = ("code", "name")


class SentenceListSerializer(serializers.ModelSerializer):
    difficulty = serializers.SerializerMethodField()
    category = CategorySerializer()

    class Meta:
        model = PracticeSentence
        fields = ("id", "text", "difficulty", "category")

    @extend_schema_field(OpenApiTypes.STR)
    def get_difficulty(self, obj):
        return DIFFICULTY_TO_API[obj.difficulty]


class SentenceDetailSerializer(SentenceListSerializer):
    target_ipa = serializers.JSONField(source="cached_ipa")

    class Meta(SentenceListSerializer.Meta):
        fields = SentenceListSerializer.Meta.fields + ("target_ipa",)


class AnalysisCreateSerializer(serializers.Serializer):
    sentence_id = serializers.IntegerField(min_value=1)
    audio = serializers.FileField()
    consent_to_store = serializers.BooleanField(default=False)


class AnalysisAcceptedSerializer(serializers.Serializer):
    analysis_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=("pending",))


class AnalysisStatusSerializer(serializers.Serializer):
    analysis_id = serializers.UUIDField()
    status = serializers.ChoiceField(
        choices=("pending", "processing", "completed", "failed")
    )


class RecommendationSerializer(SentenceListSerializer):
    reason = serializers.CharField()

    class Meta(SentenceListSerializer.Meta):
        fields = SentenceListSerializer.Meta.fields + ("reason",)


class SentenceReferenceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    text = serializers.CharField()


class PronunciationErrorSerializer(serializers.ModelSerializer):
    target_phone = serializers.SerializerMethodField()
    recognized_phone = serializers.SerializerMethodField()
    confidence = serializers.FloatField(allow_null=True)

    class Meta:
        model = PronunciationError
        fields = (
            "sequence",
            "word",
            "word_index",
            "phone_position",
            "target_phone",
            "recognized_phone",
            "operation",
            "confidence",
        )

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_target_phone(self, obj):
        return obj.target_phone or None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_recognized_phone(self, obj):
        return obj.recognized_phone or None


class CorrectionFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = CorrectionFeedback
        fields = ("summary", "content", "priority_items")


class AnalysisResultSerializer(serializers.ModelSerializer):
    analysis_id = serializers.UUIDField(source="id")
    sentence = serializers.SerializerMethodField()
    score = serializers.FloatField()
    errors = PronunciationErrorSerializer(many=True)
    feedback = serializers.SerializerMethodField()

    class Meta:
        model = PronunciationAnalysis
        fields = (
            "analysis_id",
            "sentence",
            "target_ipa",
            "recognized_ipa",
            "score",
            "errors",
            "feedback",
            "created_at",
        )

    @extend_schema_field(SentenceReferenceSerializer)
    def get_sentence(self, obj):
        return {"id": obj.sentence_id, "text": obj.sentence.text}

    @extend_schema_field(CorrectionFeedbackSerializer(allow_null=True))
    def get_feedback(self, obj):
        try:
            feedback = obj.feedback
        except CorrectionFeedback.DoesNotExist:
            return None
        return CorrectionFeedbackSerializer(feedback).data


class RecordSerializer(serializers.ModelSerializer):
    analysis_id = serializers.UUIDField(source="id")
    sentence = serializers.CharField(source="sentence.text")
    score = serializers.FloatField()
    difficulty = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    error_count = serializers.IntegerField()

    class Meta:
        model = PronunciationAnalysis
        fields = (
            "analysis_id",
            "sentence",
            "score",
            "difficulty",
            "category",
            "error_count",
            "created_at",
        )

    @extend_schema_field(OpenApiTypes.STR)
    def get_difficulty(self, obj):
        return DIFFICULTY_TO_API[obj.sentence.difficulty]

    @extend_schema_field(CategorySerializer(allow_null=True))
    def get_category(self, obj):
        if obj.sentence.category is None:
            return None
        return CategorySerializer(obj.sentence.category).data


class RecentScoreSerializer(serializers.Serializer):
    analysis_id = serializers.UUIDField()
    score = serializers.FloatField()
    created_at = serializers.DateTimeField()


class ErrorSummarySerializer(serializers.Serializer):
    category = CategorySerializer()
    count = serializers.IntegerField()


class StatisticsSummarySerializer(serializers.Serializer):
    total_analyses = serializers.IntegerField()
    average_score = serializers.FloatField()
    best_score = serializers.FloatField()
    recent_scores = RecentScoreSerializer(many=True)
    error_summary = ErrorSummarySerializer(many=True)
