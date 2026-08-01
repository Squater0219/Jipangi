from datetime import timedelta
from pathlib import Path
from time import monotonic

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import (
    CorrectionFeedback,
    PronunciationAnalysis,
    PronunciationError,
)
from .services.alignment import error_rows, pronunciation_score
from .services.analyzer import AnalyzerTemporaryError, run_analyzer


@shared_task(name="pronunciation.healthcheck")
def healthcheck():
    return "ok"


@shared_task(bind=True, max_retries=2, name="pronunciation.process_analysis")
def process_analysis(self, analysis_id, audio_path):
    started_at = monotonic()
    cleanup_audio = True
    try:
        analysis = PronunciationAnalysis.objects.select_related("sentence").get(id=analysis_id)
        analysis.status = PronunciationAnalysis.Status.PROCESSING
        analysis.failure_reason = ""
        analysis.save(update_fields=["status", "failure_reason", "updated_at"])

        result = run_analyzer(audio_path, analysis.target_ipa)
        recognized_ipa = result["recognized_ipa"]
        if not isinstance(recognized_ipa, list):
            raise ValueError("recognized_ipa는 배열이어야 합니다.")

        score, alignment = pronunciation_score(analysis.target_ipa, recognized_ipa)
        errors = error_rows(alignment, analysis.sentence.word_spans)
        completed_at = timezone.now()

        with transaction.atomic():
            analysis.recognized_ipa = recognized_ipa
            analysis.alignment = alignment
            analysis.score = score
            analysis.status = PronunciationAnalysis.Status.COMPLETED
            analysis.processing_ms = int((monotonic() - started_at) * 1000)
            analysis.analyzer_metadata = result.get("analyzer_metadata", {})
            analysis.expires_at = (
                None if analysis.consent_to_store else completed_at + timedelta(minutes=30)
            )
            analysis.save(
                update_fields=[
                    "recognized_ipa",
                    "alignment",
                    "score",
                    "status",
                    "processing_ms",
                    "analyzer_metadata",
                    "expires_at",
                    "updated_at",
                ]
            )
            PronunciationError.objects.filter(analysis=analysis).delete()
            PronunciationError.objects.bulk_create(
                [PronunciationError(analysis=analysis, **row) for row in errors]
            )
            _save_feedback(analysis, result.get("feedback"))

        _schedule_expiration(analysis)
        return {"analysis_id": str(analysis.id), "status": analysis.status}
    except PronunciationAnalysis.DoesNotExist:
        return {"analysis_id": str(analysis_id), "status": "deleted"}
    except AnalyzerTemporaryError as exc:
        if self.request.retries < self.max_retries:
            cleanup_audio = False
            raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))
        _mark_failed(analysis_id, exc, started_at)
        return {"analysis_id": str(analysis_id), "status": "failed"}
    except Exception as exc:
        _mark_failed(analysis_id, exc, started_at)
        return {"analysis_id": str(analysis_id), "status": "failed"}
    finally:
        if cleanup_audio:
            Path(audio_path).unlink(missing_ok=True)


@shared_task(name="pronunciation.delete_expired_analysis")
def delete_expired_analysis(analysis_id):
    deleted, _ = PronunciationAnalysis.objects.filter(
        id=analysis_id,
        consent_to_store=False,
        expires_at__isnull=False,
        expires_at__lte=timezone.now(),
    ).delete()
    return deleted > 0


def _save_feedback(analysis, feedback):
    if not feedback:
        return
    CorrectionFeedback.objects.update_or_create(
        analysis=analysis,
        defaults={
            "summary": feedback.get("summary", "발음 분석이 완료되었습니다."),
            "content": feedback.get("content", ""),
            "priority_items": feedback.get("priority_items", []),
            "structured_output": feedback.get("structured_output", {}),
            "model_name": feedback.get("model_name", ""),
            "model_version": feedback.get("model_version", ""),
            "is_validated": feedback.get("is_validated", False),
        },
    )


def _mark_failed(analysis_id, exc, started_at):
    try:
        analysis = PronunciationAnalysis.objects.get(id=analysis_id)
    except PronunciationAnalysis.DoesNotExist:
        return

    failed_at = timezone.now()
    analysis.status = PronunciationAnalysis.Status.FAILED
    analysis.failure_reason = f"{type(exc).__name__}: {exc}"[:2000]
    analysis.processing_ms = int((monotonic() - started_at) * 1000)
    analysis.expires_at = None if analysis.consent_to_store else failed_at + timedelta(minutes=30)
    analysis.save(
        update_fields=[
            "status",
            "failure_reason",
            "processing_ms",
            "expires_at",
            "updated_at",
        ]
    )
    _schedule_expiration(analysis)


def _schedule_expiration(analysis):
    if analysis.expires_at is not None:
        delete_expired_analysis.apply_async(args=[str(analysis.id)], eta=analysis.expires_at)
