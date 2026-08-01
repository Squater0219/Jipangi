from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from pronunciation.models import (
    CorrectionFeedback,
    PracticeSentence,
    PronunciationAnalysis,
    PronunciationCategory,
    PronunciationError,
)
from pronunciation.tasks import delete_expired_analysis


class PronunciationModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="user@example.com",
            username="사용자",
            password="safe-password-1234",
        )
        cls.category = PronunciationCategory.objects.create(code="batchim", name="받침")
        cls.sentence = PracticeSentence.objects.create(
            text="학교에 갑니다.",
            cached_ipa=["h", "a", "k̚", "k͈", "j", "o", "e", "k", "a", "m", "n", "i", "d", "a"],
            difficulty=PracticeSentence.Difficulty.BEGINNER,
            category=cls.category,
        )

    def test_complete_analysis_graph(self):
        analysis = PronunciationAnalysis.objects.create(
            user=self.user,
            sentence=self.sentence,
            target_ipa=["h", "a", "k̚", "k͈", "j", "o", "e", "k", "a", "m", "n", "i", "d", "a"],
            recognized_ipa=[
                "h",
                "a",
                "k̚",
                "k͈",
                "j",
                "o",
                "e",
                "k",
                "a",
                "p",
                "n",
                "i",
                "d",
                "a",
            ],
            score=Decimal("93.5"),
            status=PronunciationAnalysis.Status.COMPLETED,
            consent_to_store=True,
            analyzer_metadata={"inventory_version": "ko-v1"},
        )
        error = PronunciationError.objects.create(
            analysis=analysis,
            sequence=0,
            phone_position=8,
            word="갑니다",
            word_index=1,
            target_phone="m",
            recognized_phone="p",
            operation=PronunciationError.Operation.SUBSTITUTION,
            confidence=Decimal("0.8700"),
        )
        feedback = CorrectionFeedback.objects.create(
            analysis=analysis,
            summary="입술을 닫고 코로 울려 보세요.",
            content="'갑니다'의 ㅁ 발음을 먼저 연습하세요.",
            priority_items=[{"error_sequence": 0, "priority": 1}],
        )

        self.assertEqual(analysis.errors.get(), error)
        self.assertEqual(analysis.feedback, feedback)
        self.assertEqual(self.sentence.analyses.count(), 1)

    def test_score_validation_rejects_out_of_range_value(self):
        analysis = PronunciationAnalysis(
            user=self.user,
            sentence=self.sentence,
            target_ipa=["t", "e", "s", "t"],
            score=Decimal("101.0"),
        )
        with self.assertRaises(ValidationError):
            analysis.full_clean()

    def test_analysis_without_storage_consent_is_allowed_temporarily(self):
        analysis = PronunciationAnalysis.objects.create(
            user=self.user,
            sentence=self.sentence,
            target_ipa=["t", "e", "s", "t"],
        )

        self.assertFalse(analysis.consent_to_store)

    def test_processing_status_is_supported(self):
        analysis = PronunciationAnalysis.objects.create(
            user=self.user,
            sentence=self.sentence,
            target_ipa=["t", "e", "s", "t"],
            status=PronunciationAnalysis.Status.PROCESSING,
        )

        self.assertEqual(analysis.status, "processing")

    def test_expired_analysis_without_consent_is_deleted(self):
        analysis = PronunciationAnalysis.objects.create(
            user=self.user,
            sentence=self.sentence,
            target_ipa=["t", "e", "s", "t"],
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        deleted = delete_expired_analysis.run(str(analysis.id))

        self.assertTrue(deleted)
        self.assertFalse(PronunciationAnalysis.objects.filter(id=analysis.id).exists())

    def test_error_sequence_is_unique_per_analysis(self):
        analysis = PronunciationAnalysis.objects.create(
            user=self.user,
            sentence=self.sentence,
            target_ipa=["t", "e", "s", "t"],
        )
        PronunciationError.objects.create(
            analysis=analysis,
            sequence=0,
            phone_position=0,
            operation=PronunciationError.Operation.DELETION,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            PronunciationError.objects.create(
                analysis=analysis,
                sequence=0,
                phone_position=1,
                operation=PronunciationError.Operation.INSERTION,
            )
