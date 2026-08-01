from django.urls import path

from .views import (
    AnalysisCreateView,
    AnalysisResultView,
    AnalysisStatusView,
    RecordListView,
    SentenceDetailView,
    SentenceListView,
    SentenceRecommendationView,
    StatisticsSummaryView,
)


urlpatterns = [
    path("sentences", SentenceListView.as_view(), name="sentence-list"),
    path(
        "sentences/recommendation",
        SentenceRecommendationView.as_view(),
        name="sentence-recommendation",
    ),
    path(
        "sentences/<int:sentence_id>",
        SentenceDetailView.as_view(),
        name="sentence-detail",
    ),
    path("analyses", AnalysisCreateView.as_view(), name="analysis-create"),
    path(
        "analyses/<uuid:analysis_id>/status",
        AnalysisStatusView.as_view(),
        name="analysis-status",
    ),
    path(
        "analyses/<uuid:analysis_id>",
        AnalysisResultView.as_view(),
        name="analysis-result",
    ),
    path("records", RecordListView.as_view(), name="record-list"),
    path(
        "statistics/summary",
        StatisticsSummaryView.as_view(),
        name="statistics-summary",
    ),
]
