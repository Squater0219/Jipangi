from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from pronunciation.models import PracticeSentence, PronunciationCategory


class SentenceAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = PronunciationCategory.objects.create(code="batchim", name="받침")
        cls.easy_sentence = PracticeSentence.objects.create(
            text="안녕하세요.",
            cached_ipa=["a", "n", "n", "j", "ʌ", "ŋ"],
            difficulty=PracticeSentence.Difficulty.BEGINNER,
            category=cls.category,
        )
        cls.hard_sentence = PracticeSentence.objects.create(
            text="값이 비쌉니다.",
            cached_ipa=["k", "a", "p̚"],
            difficulty=PracticeSentence.Difficulty.ADVANCED,
            category=cls.category,
        )
        PracticeSentence.objects.create(
            text="비활성 문장",
            difficulty=PracticeSentence.Difficulty.BEGINNER,
            category=cls.category,
            is_active=False,
        )
        cls.user = get_user_model().objects.create_user(
            email="user@example.com",
            username="사용자",
            password="safe-password-1234",
        )

    def authenticate(self):
        access = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_sentence_list_is_public_and_filters_difficulty(self):
        response = self.client.get("/api/v1/sentences", {"difficulty": "easy"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["difficulty"], "easy")

    def test_sentence_detail_returns_ipa_array(self):
        response = self.client.get(f"/api/v1/sentences/{self.easy_sentence.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["target_ipa"], ["a", "n", "n", "j", "ʌ", "ŋ"])

    def test_inactive_sentence_is_not_found(self):
        inactive = PracticeSentence.objects.get(text="비활성 문장")

        response = self.client.get(f"/api/v1/sentences/{inactive.id}")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"]["code"], "SENTENCE_NOT_FOUND")

    def test_invalid_difficulty_uses_common_error(self):
        response = self.client.get("/api/v1/sentences", {"difficulty": "unknown"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "INVALID_REQUEST")

    def test_user_without_history_receives_easy_recommendation(self):
        self.authenticate()

        response = self.client.get("/api/v1/sentences/recommendation")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["difficulty"], "easy")
