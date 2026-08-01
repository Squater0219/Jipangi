import io
import wave

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from pronunciation.models import PracticeSentence, PronunciationAnalysis, PronunciationCategory


def wav_file():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 1600)
    buffer.seek(0)
    buffer.name = "voice.wav"
    return buffer


class AnalysisAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        category = PronunciationCategory.objects.create(code="batchim", name="받침")
        cls.sentence = PracticeSentence.objects.create(
            text="안녕하세요.",
            cached_ipa=["a", "n", "n", "j", "ʌ", "ŋ"],
            word_spans=[{"word": "안녕하세요", "start": 0, "end": 6}],
            category=category,
        )
        cls.user = get_user_model().objects.create_user(
            email="user@example.com",
            username="사용자",
            password="safe-password-1234",
        )
        cls.other_user = get_user_model().objects.create_user(
            email="other@example.com",
            username="다른사용자",
            password="safe-password-1234",
        )

    def authenticate(self, user=None):
        access = RefreshToken.for_user(user or self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def create_analysis(self, consent=False):
        return self.client.post(
            "/api/v1/analyses",
            {
                "sentence_id": self.sentence.id,
                "audio": wav_file(),
                "consent_to_store": consent,
            },
            format="multipart",
        )

    def test_create_status_and_result_flow(self):
        self.authenticate()

        created = self.create_analysis(consent=False)

        self.assertEqual(created.status_code, 202)
        analysis_id = created.data["analysis_id"]
        status_response = self.client.get(f"/api/v1/analyses/{analysis_id}/status")
        self.assertEqual(status_response.data["status"], "completed")

        result_response = self.client.get(f"/api/v1/analyses/{analysis_id}")
        self.assertEqual(result_response.status_code, 200)
        self.assertEqual(result_response.data["score"], 100.0)
        self.assertEqual(result_response.data["recognized_ipa"], self.sentence.cached_ipa)

        analysis = PronunciationAnalysis.objects.get(id=analysis_id)
        self.assertIsNotNone(analysis.expires_at)
        self.assertEqual(analysis.analyzer_metadata["backend"], "development-stub")

    def test_analysis_is_private_and_can_be_deleted(self):
        self.authenticate()
        created = self.create_analysis(consent=True)
        analysis_id = created.data["analysis_id"]

        self.authenticate(self.other_user)
        forbidden = self.client.get(f"/api/v1/analyses/{analysis_id}")
        self.assertEqual(forbidden.status_code, 404)
        self.assertEqual(forbidden.data["error"]["code"], "ANALYSIS_NOT_FOUND")

        self.authenticate()
        deleted = self.client.delete(f"/api/v1/analyses/{analysis_id}")
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(PronunciationAnalysis.objects.filter(id=analysis_id).exists())

    def test_missing_audio_has_specific_error(self):
        self.authenticate()

        response = self.client.post(
            "/api/v1/analyses",
            {"sentence_id": self.sentence.id},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "AUDIO_FILE_REQUIRED")

    def test_invalid_audio_is_rejected(self):
        self.authenticate()
        invalid = io.BytesIO(b"not audio")
        invalid.name = "voice.wav"

        response = self.client.post(
            "/api/v1/analyses",
            {"sentence_id": self.sentence.id, "audio": invalid},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "INVALID_AUDIO_FORMAT")
