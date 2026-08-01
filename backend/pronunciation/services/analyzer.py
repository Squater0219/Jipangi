from django.conf import settings
from django.utils.module_loading import import_string


class AnalyzerTemporaryError(Exception):
    pass


def run_analyzer(audio_path, target_ipa):
    backend = import_string(settings.PRONUNCIATION_ANALYZER_BACKEND)
    return backend(audio_path=audio_path, target_ipa=target_ipa)


def development_analyzer(*, audio_path, target_ipa):
    return {
        "recognized_ipa": list(target_ipa),
        "analyzer_metadata": {
            "backend": "development-stub",
            "warning": "실제 음성 분석 결과가 아닙니다.",
        },
        "feedback": {
            "summary": "개발용 분석이 완료되었습니다.",
            "content": "현재 개발 환경에서는 목표 IPA를 그대로 반환합니다.",
            "priority_items": [],
            "structured_output": {"development_stub": True},
            "model_name": "",
            "model_version": "",
            "is_validated": False,
        },
    }
