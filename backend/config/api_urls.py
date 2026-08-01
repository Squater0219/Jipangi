from django.urls import include, path


app_name = "api_v1"

urlpatterns = [
    path("", include("users.urls")),
    path("", include("pronunciation.urls")),
]
