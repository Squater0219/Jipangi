from django.contrib import admin

from .models import (
    CorrectionFeedback,
    PracticeSentence,
    PronunciationAnalysis,
    PronunciationCategory,
    PronunciationError,
)


@admin.register(PronunciationCategory)
class PronunciationCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "updated_at")
    search_fields = ("name", "code")


@admin.register(PracticeSentence)
class PracticeSentenceAdmin(admin.ModelAdmin):
    list_display = ("text", "difficulty", "category", "is_active", "updated_at")
    list_filter = ("difficulty", "category", "is_active")
    search_fields = ("text",)


class PronunciationErrorInline(admin.TabularInline):
    model = PronunciationError
    extra = 0


class CorrectionFeedbackInline(admin.StackedInline):
    model = CorrectionFeedback
    extra = 0
    max_num = 1


@admin.register(PronunciationAnalysis)
class PronunciationAnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "sentence", "status", "score", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "user__username", "sentence__text")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (PronunciationErrorInline, CorrectionFeedbackInline)


@admin.register(PronunciationError)
class PronunciationErrorAdmin(admin.ModelAdmin):
    list_display = ("analysis", "sequence", "word", "operation", "target_phone", "recognized_phone")
    list_filter = ("operation",)
    search_fields = ("word", "target_phone", "recognized_phone")


@admin.register(CorrectionFeedback)
class CorrectionFeedbackAdmin(admin.ModelAdmin):
    list_display = ("analysis", "summary", "model_name", "is_validated", "created_at")
    list_filter = ("is_validated", "model_name")
    search_fields = ("summary", "content")
