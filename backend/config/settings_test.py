from .settings import *  # noqa: F403


# 모델과 마이그레이션 로직을 외부 MySQL 상태와 분리해 빠르게 검증한다.
# 개발·운영 설정(config.settings)은 항상 MySQL을 사용한다.
DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
