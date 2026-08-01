import hashlib
import wave
from pathlib import Path
from uuid import uuid4

import filetype
from django.conf import settings
from mutagen import File as MutagenFile

from config.exceptions import APIError


MAX_AUDIO_SIZE = 20 * 1024 * 1024
MAX_AUDIO_DURATION = 30
ALLOWED_EXTENSIONS = {"wav", "m4a", "aac"}
ALLOWED_MIME_TYPES = {
    "audio/aac",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "video/mp4",
}


def calculate_request_fingerprint(*, user_id, sentence_id, audio_path):
    digest = hashlib.sha256()
    digest.update(str(user_id).encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(sentence_id).encode("utf-8"))
    digest.update(b"\0")
    with Path(audio_path).open("rb") as audio:
        for chunk in iter(lambda: audio.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_audio(uploaded_file):
    extension = Path(uploaded_file.name).suffix.lower().lstrip(".")
    if uploaded_file.size > MAX_AUDIO_SIZE:
        _audio_error("AUDIO_TOO_LARGE", "음성 파일은 20MB 이하여야 합니다.")
    if extension not in ALLOWED_EXTENSIONS:
        _audio_error("INVALID_AUDIO_FORMAT", "지원하지 않는 음성 파일 형식입니다.")

    header = uploaded_file.read(4096)
    uploaded_file.seek(0)
    kind = filetype.guess(header)
    if kind is None or kind.mime not in ALLOWED_MIME_TYPES:
        _audio_error("INVALID_AUDIO_FORMAT", "음성 파일의 실제 형식을 확인할 수 없습니다.")

    path = _write_temporary_audio(uploaded_file, extension)
    try:
        duration = _audio_duration(path, extension)
        if duration > MAX_AUDIO_DURATION:
            _audio_error("AUDIO_TOO_LONG", "음성 길이는 30초 이하여야 합니다.")
    except APIError:
        Path(path).unlink(missing_ok=True)
        raise
    except Exception as exc:
        Path(path).unlink(missing_ok=True)
        raise APIError(
            status_code=400,
            code="INVALID_AUDIO_FORMAT",
            message="음성 파일을 읽을 수 없습니다.",
        ) from exc
    return path


def _write_temporary_audio(uploaded_file, extension):
    directory = Path(settings.MEDIA_ROOT) / "audio_tmp"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4().hex}.{extension}"
    with path.open("wb") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
    uploaded_file.seek(0)
    return str(path)


def _audio_duration(path, extension):
    if extension == "wav":
        with wave.open(path, "rb") as audio:
            return audio.getnframes() / audio.getframerate()

    audio = MutagenFile(path)
    if audio is None or audio.info is None:
        raise ValueError("오디오 메타데이터를 읽을 수 없습니다.")
    return float(audio.info.length)


def _audio_error(code, message):
    raise APIError(status_code=400, code=code, message=message)
