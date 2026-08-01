import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PronunciationCategory(TimeStampedModel):
    code = models.SlugField(max_length=50, unique=True, verbose_name="분류 코드")
    name = models.CharField(max_length=100, unique=True, verbose_name="분류명")
    description = models.TextField(blank=True, verbose_name="설명")

    class Meta:
        db_table = "pronunciation_category"
        ordering = ["name"]
        verbose_name = "발음 분류"
        verbose_name_plural = "발음 분류"

    def __str__(self):
        return self.name


class PracticeSentence(TimeStampedModel):
    class Difficulty(models.IntegerChoices):
        BEGINNER = 1, "초급"
        INTERMEDIATE = 2, "중급"
        ADVANCED = 3, "고급"

    text = models.CharField(max_length=255, unique=True, verbose_name="연습 문장")
    cached_ipa = models.JSONField(
        default=list,
        blank=True,
        verbose_name="목표 IPA 캐시",
        help_text='예: ["h", "a", "k̚", "k͈", "j", "o"]',
    )
    word_spans = models.JSONField(
        default=list,
        blank=True,
        verbose_name="단어-음소 위치 매핑",
        help_text='예: [{"word": "갑니다", "start": 0, "end": 7}]',
    )
    difficulty = models.PositiveSmallIntegerField(
        choices=Difficulty.choices,
        default=Difficulty.BEGINNER,
        verbose_name="난이도",
    )
    category = models.ForeignKey(
        PronunciationCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sentences",
        verbose_name="발음 분류",
    )
    is_active = models.BooleanField(default=True, verbose_name="사용 여부")

    class Meta:
        db_table = "practice_sentence"
        ordering = ["difficulty", "id"]
        indexes = [
            models.Index(fields=["is_active", "difficulty"], name="sentence_active_diff_idx"),
            models.Index(fields=["category", "is_active"], name="sentence_category_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(difficulty__in=[1, 2, 3]),
                name="sentence_valid_difficulty",
            )
        ]
        verbose_name = "연습 문장"
        verbose_name_plural = "연습 문장"

    def __str__(self):
        return self.text


class PronunciationAnalysis(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "분석 대기"
        PROCESSING = "processing", "분석 중"
        COMPLETED = "completed", "분석 완료"
        FAILED = "failed", "분석 실패"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pronunciation_analyses",
        verbose_name="사용자",
    )
    sentence = models.ForeignKey(
        PracticeSentence,
        on_delete=models.PROTECT,
        related_name="analyses",
        verbose_name="연습 문장",
    )
    target_ipa = models.JSONField(default=list, verbose_name="목표 IPA")
    recognized_ipa = models.JSONField(default=list, blank=True, verbose_name="사용자 IPA")
    alignment = models.JSONField(default=list, blank=True, verbose_name="IPA 정렬 결과")
    score = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="발음 점수",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="분석 상태",
    )
    consent_to_store = models.BooleanField(
        default=False,
        verbose_name="기록 저장 동의",
        help_text="미동의 분석 결과는 완료 후 30분 동안만 임시 보관합니다.",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="임시 결과 만료 시각",
    )
    processing_ms = models.PositiveIntegerField(null=True, blank=True, verbose_name="처리 시간(ms)")
    analyzer_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="분석기 메타데이터",
        help_text="G2P, Allosaurus, inventory 버전 등 재현에 필요한 정보",
    )
    failure_reason = models.TextField(blank=True, verbose_name="실패 사유")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pronunciation_analysis"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="analysis_user_date_idx"),
            models.Index(fields=["sentence", "-created_at"], name="analysis_sentence_idx"),
            models.Index(fields=["status", "-created_at"], name="analysis_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(score__isnull=True) | (Q(score__gte=0) & Q(score__lte=100)),
                name="analysis_score_0_to_100",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "pending",
                        "processing",
                        "completed",
                        "failed",
                    ]
                ),
                name="analysis_valid_status",
            ),
        ]
        verbose_name = "발음 분석 기록"
        verbose_name_plural = "발음 분석 기록"

    def __str__(self):
        return f"{self.sentence_id} - {self.created_at:%Y-%m-%d %H:%M}"


class PronunciationError(models.Model):
    class Operation(models.TextChoices):
        SUBSTITUTION = "substitution", "대체"
        DELETION = "deletion", "삭제"
        INSERTION = "insertion", "삽입"
        WEAKENING = "weakening", "약화"

    analysis = models.ForeignKey(
        PronunciationAnalysis,
        on_delete=models.CASCADE,
        related_name="errors",
        verbose_name="분석 기록",
    )
    sequence = models.PositiveIntegerField(verbose_name="오류 순서")
    phone_position = models.PositiveIntegerField(verbose_name="목표 IPA 위치")
    word = models.CharField(max_length=100, blank=True, verbose_name="오류 단어")
    word_index = models.PositiveIntegerField(null=True, blank=True, verbose_name="문장 내 단어 위치")
    target_phone = models.CharField(max_length=20, blank=True, verbose_name="목표 음소")
    recognized_phone = models.CharField(max_length=20, blank=True, verbose_name="인식 음소")
    operation = models.CharField(max_length=20, choices=Operation.choices, verbose_name="오류 유형")
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        verbose_name="인식 신뢰도",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pronunciation_error"
        ordering = ["sequence"]
        indexes = [
            models.Index(fields=["analysis", "operation"], name="error_analysis_op_idx"),
            models.Index(fields=["target_phone", "recognized_phone"], name="error_phone_pair_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["analysis", "sequence"], name="error_unique_sequence"),
            models.CheckConstraint(
                condition=Q(confidence__isnull=True)
                | (Q(confidence__gte=0) & Q(confidence__lte=1)),
                name="error_confidence_0_to_1",
            ),
        ]
        verbose_name = "발음 오류"
        verbose_name_plural = "발음 오류"

    def __str__(self):
        return f"{self.get_operation_display()}: {self.target_phone} → {self.recognized_phone}"


class CorrectionFeedback(models.Model):
    analysis = models.OneToOneField(
        PronunciationAnalysis,
        on_delete=models.CASCADE,
        related_name="feedback",
        verbose_name="분석 기록",
    )
    summary = models.CharField(max_length=500, verbose_name="피드백 요약")
    content = models.TextField(verbose_name="교정 피드백")
    priority_items = models.JSONField(default=list, blank=True, verbose_name="교정 우선순위")
    structured_output = models.JSONField(default=dict, blank=True, verbose_name="LLM 구조화 출력")
    model_name = models.CharField(max_length=100, blank=True, verbose_name="LLM 모델명")
    model_version = models.CharField(max_length=100, blank=True, verbose_name="LLM 모델 버전")
    is_validated = models.BooleanField(default=False, verbose_name="규칙 검증 통과 여부")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "correction_feedback"
        verbose_name = "교정 피드백"
        verbose_name_plural = "교정 피드백"

    def __str__(self):
        return self.summary
