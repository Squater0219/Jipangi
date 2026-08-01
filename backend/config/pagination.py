from urllib.parse import urlsplit

from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination

from config.exceptions import APIError


class StandardPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        try:
            return super().paginate_queryset(queryset, request, view=view)
        except NotFound as exc:
            raise APIError(
                status_code=400,
                code="INVALID_PAGE",
                message="페이지 또는 페이지 크기가 올바르지 않습니다.",
            ) from exc

    def get_next_link(self):
        return self._relative(super().get_next_link())

    def get_previous_link(self):
        return self._relative(super().get_previous_link())

    @staticmethod
    def _relative(url):
        if url is None:
            return None
        parsed = urlsplit(url)
        return f"{parsed.path}?{parsed.query}" if parsed.query else parsed.path
