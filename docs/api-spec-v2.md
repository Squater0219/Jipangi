# 발음 교정 서비스 API 명세 v2

이 문서는 팀장 전달 명세를 백엔드 구현 기준에 맞게 정리한 확정 API 명세이다. 별도의 변경 합의가 없는 한 이 문서를 기준으로 Django 서버와 클라이언트를 구현한다.

문서 상태: 기존 API 엔드포인트 구현 완료, AI 교정 피드백 생성 API는 명세만
확정하고 구현 전

현재 개발 환경의 분석 어댑터는 프론트엔드 연동 테스트를 위한 임시 구현이다. 업로드된 음성을 실제로 판정하지 않고 목표 IPA를 인식 IPA로 반환하므로 점수는 항상 100점이다. 실제 분석 모듈이 준비되면 `PRONUNCIATION_ANALYZER_BACKEND` 환경 변수만 실제 함수 경로로 변경한다.

프론트엔드 코드 생성이나 API 도구 가져오기가 필요한 경우 같은 디렉터리의
`openapi.yaml`을 사용한다. 단, AI 교정 피드백 생성 API는 아직 이 Markdown
명세에만 반영되어 있으므로 구현 시 OpenAPI 문서도 함께 갱신해야 한다.

## 공통 규칙

- Base URL: `/api/v1`
- 요청 및 응답 형식: 별도 표기가 없으면 `application/json`
- 인증 방식: `Authorization: Bearer {access_token}`
- 날짜 저장 기준: UTC
- 날짜 응답 형식: UTC 기준 ISO 8601 문자열
- 사용자 ID, 문장 ID: 정수
- 분석 ID: UUID v4 문자열
- 난이도 값: `easy`, `normal`, `hard`
- 카테고리 값: `batchim`, `liaison`, `nasalization`, `liquidization`, `tensification`, `palatalization`
- 페이지네이션 기본 크기: 20개
- 페이지네이션 최대 크기: 100개
- 점수 범위: `0.0` 이상 `100.0` 이하, 소수점 한 자리
- IPA 형식: 음소 단위의 유니코드 IPA 문자열 배열

## 구현 확정 사항

- 사용자 모델은 개발 시작부터 Custom User를 사용한다. 이메일을 로그인 ID로 사용하고 고유값으로 관리하며, `username`은 화면에 표시할 이름으로 사용한다.
- JWT 구현은 `djangorestframework-simplejwt`를 사용하고 blacklist 앱을 활성화한다.
- Access Token 유효기간은 30분, Refresh Token 유효기간은 7일로 한다.
- Refresh Token을 사용할 때마다 새 Refresh Token을 발급하고 기존 토큰은 블랙리스트에 등록한다.
- 분석 작업은 Celery와 Redis를 사용해 비동기로 처리한다. Django API 서버는 분석 요청을 등록한 뒤 즉시 분석 ID를 반환한다.
- IPA는 음소 하나를 배열 요소 하나로 표현한다. Django 모델에서는 `JSONField`로 관리한다.
- 분석 점수는 목표 IPA와 인식 IPA의 Levenshtein distance를 사용해 계산한다. 계산식은 `max(0, (1 - distance / target_length) * 100)`이며 소수점 한 자리로 반올림한다.
- 목표 IPA가 비어 있으면 점수를 계산하지 않고 분석을 `failed`로 처리한다.
- 음성 파일은 분석 완료 또는 실패 직후 삭제하며 영구 보관하지 않는다.
- 저장에 동의하지 않은 분석 결과는 사용자에게 결과를 전달하기 위해 완료 시점부터 30분 동안만 임시 보관한 뒤 삭제한다. 해당 결과는 학습 기록, 추천 및 통계에 사용하지 않는다.
- 저장에 동의한 분석 결과는 사용자가 분석 결과 삭제 API를 호출하기 전까지 보관한다.
- 연습 문장과 카테고리는 Django 관리자 페이지에서 추가, 수정 및 비활성화할 수 있게 한다.
- 운영 환경에서는 HTTPS만 허용하고 JWT 서명 키와 DB 비밀번호는 환경 변수로 관리한다.
- CORS는 환경 변수에 등록된 프론트엔드 Origin만 허용하며 전체 Origin 허용은 사용하지 않는다.

공통 응답 에러 형식은 다음과 같다.

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "요청 형식이 올바르지 않습니다.",
    "details": {}
  }
}
```

## 1. 회원가입

`POST /api/v1/auth/signup`

인증이 필요하지 않다.

요청:

```json
{
  "username": "user1",
  "email": "user@example.com",
  "password": "password1234"
}
```

응답:

```json
{
  "access_token": "access.jwt.token",
  "refresh_token": "refresh.jwt.token",
  "user": {
    "id": 1,
    "username": "user1",
    "email": "user@example.com"
  }
}
```

구현 기준:

- 성공 시 HTTP `201 Created`를 반환한다.
- 이메일은 필수이며 중복될 수 없다.
- 이메일은 소문자로 정규화해서 저장한다.
- 사용자 이름은 2자 이상 30자 이하이며 중복을 허용한다.
- 비밀번호는 8자 이상으로 제한하고 Django 비밀번호 검증 규칙을 적용한 뒤 해시 처리해서 저장한다.
- 회원가입이 성공하면 바로 로그인 상태가 되도록 Access Token과 Refresh Token을 함께 반환한다.
- 회원가입 요청은 IP 기준으로 1시간에 5회로 제한한다.

변경점: 기존 명세에는 회원가입 후 토큰 반환 여부가 없었으므로, 가입 직후 토큰을 반환하는 방식으로 확정했다.

## 2. 로그인

`POST /api/v1/auth/login`

인증이 필요하지 않다.

요청:

```json
{
  "email": "user@example.com",
  "password": "password1234"
}
```

응답:

```json
{
  "access_token": "access.jwt.token",
  "refresh_token": "refresh.jwt.token",
  "user": {
    "id": 1,
    "username": "user1",
    "email": "user@example.com"
  }
}
```

구현 기준:

- Custom User 모델과 이메일 인증 백엔드를 사용해 이메일 기준으로 로그인한다.
- 이메일 또는 비밀번호가 틀린 경우 같은 에러 메시지를 반환한다.
- 로그인 요청은 IP와 이메일을 기준으로 각각 1분에 5회로 제한한다.

변경점: 기존 명세는 이메일 로그인을 요구하지만 Django 기본 로그인과 맞지 않았으므로, 이메일 고유값과 이메일 인증 로직을 기준으로 수정했다.

## 3. JWT 토큰 갱신

`POST /api/v1/auth/token/refresh`

Access Token 없이 호출할 수 있다.

요청:

```json
{
  "refresh_token": "refresh.jwt.token"
}
```

응답:

```json
{
  "access_token": "new.access.jwt.token",
  "refresh_token": "new.refresh.jwt.token"
}
```

구현 기준:

- Refresh Token이 유효하면 새 Access Token과 Refresh Token을 발급한다.
- 기존 Refresh Token은 블랙리스트 처리한다.
- 만료되었거나 이미 사용된 Refresh Token은 `401 INVALID_TOKEN`을 반환한다.

변경점: 기존 명세에는 Access Token 만료 후 갱신 API가 없었으므로 새로 추가했다.

## 4. 로그아웃

`POST /api/v1/auth/logout`

인증이 필요하다.

요청:

```json
{
  "refresh_token": "refresh.jwt.token"
}
```

응답:

```http
204 No Content
```

구현 기준:

- 전달받은 Refresh Token을 블랙리스트에 등록한다.
- 로그아웃 후 해당 Refresh Token으로는 토큰 갱신이 불가능해야 한다.
- Access Token은 서버에 저장하지 않으므로 클라이언트에서 즉시 제거한다. 이미 발급된 Access Token은 최대 30분 뒤 만료된다.

변경점: 기존 명세에는 로그아웃과 Refresh Token 폐기 방식이 없었으므로 새로 추가했다.

## 5. 연습 문장 목록 조회

`GET /api/v1/sentences`

인증이 필요하지 않다.

쿼리 파라미터:

- `category`: 카테고리 코드
- `difficulty`: `easy`, `normal`, `hard`
- `page`: 페이지 번호
- `page_size`: 페이지 크기

응답:

```json
{
  "count": 24,
  "next": "/api/v1/sentences?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "text": "안녕하세요.",
      "difficulty": "easy",
      "category": {
        "code": "batchim",
        "name": "받침"
      }
    }
  ]
}
```

구현 기준:

- 활성화된 문장만 반환한다.
- 난이도는 API에서는 문자열로 반환한다.
- DB에서는 `PositiveSmallIntegerField`로 관리하며 `1=easy`, `2=normal`, `3=hard`로 고정한다.
- `page_size`는 1 이상 100 이하이며 생략하면 20으로 처리한다.

변경점: 기존 명세의 페이지네이션 형식에 `next`, `previous`를 추가하고 난이도 표현 방식을 확정했다.

## 6. 연습 문장 상세 조회

`GET /api/v1/sentences/{sentence_id}`

인증이 필요하지 않다.

응답:

```json
{
  "id": 1,
  "text": "안녕하세요.",
  "difficulty": "easy",
  "category": {
    "code": "batchim",
    "name": "받침"
  },
  "target_ipa": ["a", "n", "n", "j", "ʌ", "ŋ"]
}
```

구현 기준:

- 존재하지 않는 문장 ID는 `404 SENTENCE_NOT_FOUND`를 반환한다.
- 비활성화된 문장은 조회되지 않는다.
- IPA 배열의 각 요소는 분석 정렬에 사용하는 음소 하나를 의미한다.

변경점: 기존 명세의 기본 구조는 유지하고, IPA를 배열 형식으로 내려주는 방식으로 정리했다.

## 7. 추천 문장 조회

`GET /api/v1/sentences/recommendation`

인증이 필요하다.

응답:

```json
{
  "id": 3,
  "text": "학교에 갑니다.",
  "difficulty": "normal",
  "category": {
    "code": "liaison",
    "name": "연음"
  },
  "reason": "최근 연음 오류가 많아 해당 유형의 문장을 추천합니다."
}
```

구현 기준:

- 저장에 동의한 사용자의 완료된 분석 기록만 기준으로 추천한다.
- 오류가 많이 발생한 카테고리의 문장을 우선 추천한다.
- 최근 30개 분석에서 오류 수가 가장 많은 카테고리를 우선한다.
- 해당 카테고리 안에서는 아직 분석하지 않은 활성 문장을 무작위로 선택한다.
- 기록이 없거나 조건에 맞는 문장이 없으면 쉬운 난이도의 활성 문장을 무작위로 추천한다.

변경점: 기존 명세의 추천 기능은 유지하되, 추천 기준을 완료된 분석 기록 기반으로 구체화했다.

## 8. 발음 분석 요청

`POST /api/v1/analyses`

인증이 필요하다.

요청 형식은 `multipart/form-data`이다.

요청:

```text
sentence_id: 1
audio: audio file
consent_to_store: true
```

응답:

```json
{
  "analysis_id": "9f6d6c5e-33c4-4c83-989d-67b828ca4f6f",
  "status": "pending"
}
```

구현 기준:

- 성공 시 HTTP `202 Accepted`를 반환한다.
- 사용자는 JWT에서 식별한다.
- 지원 파일 형식은 `wav`, `m4a`, `aac`로 제한한다.
- 파일 크기는 20MB 이하로 제한한다.
- 음성 길이는 30초 이하로 제한한다.
- 확장자만 확인하지 않고 실제 MIME 타입과 파일 내용을 검사한다.
- 분석 요청 직후 상태는 `pending`으로 저장한다.
- Celery 작업이 시작되면 상태를 `processing`으로 변경한다.
- 분석이 완료되면 `completed`, 실패하면 `failed`로 변경한다.
- 일시적인 분석 오류는 최대 2회 재시도한 뒤 `failed`로 처리한다.
- 분석용 음성 파일은 분석 완료 또는 실패 후 즉시 삭제한다.
- `consent_to_store`의 기본값은 `false`이며 생략해도 저장에 동의하지 않은 것으로 처리한다.
- `consent_to_store`가 `false`이면 기록, 추천 및 통계에 포함하지 않고 완료 시점부터 30분 후 결과를 삭제한다.

변경점: 기존 명세에는 저장 동의와 음성 파일 보관 기준이 없었으므로 `consent_to_store`와 삭제 정책을 추가했다.

## 9. 분석 상태 조회

`GET /api/v1/analyses/{analysis_id}/status`

인증이 필요하다.

응답:

```json
{
  "analysis_id": "9f6d6c5e-33c4-4c83-989d-67b828ca4f6f",
  "status": "processing"
}
```

구현 기준:

- 상태 값은 `pending`, `processing`, `completed`, `failed` 중 하나이다.
- 본인 분석만 조회할 수 있다.
- 다른 사용자의 분석 ID는 `404 ANALYSIS_NOT_FOUND`로 처리한다.
- 저장에 동의하지 않은 결과가 보관 시간 경과로 삭제된 경우에도 `404 ANALYSIS_NOT_FOUND`를 반환한다.

변경점: 기존 명세의 `processing` 상태를 DB 상태 값에도 포함하도록 맞췄다.

## 10. 분석 결과 조회

`GET /api/v1/analyses/{analysis_id}`

인증이 필요하다.

응답:

```json
{
  "analysis_id": "9f6d6c5e-33c4-4c83-989d-67b828ca4f6f",
  "sentence": {
    "id": 1,
    "text": "안녕하세요."
  },
  "target_ipa": ["a", "n", "n", "j", "ʌ", "ŋ"],
  "recognized_ipa": ["a", "n", "j", "ʌ", "ŋ"],
  "score": 82.5,
  "feedback_status": "completed",
  "errors": [
    {
      "sequence": 1,
      "word": "안녕하세요",
      "word_index": 0,
      "phone_position": 2,
      "target_phone": "n",
      "recognized_phone": null,
      "operation": "deletion",
      "confidence": 0.91
    }
  ],
  "feedback": {
    "summary": "받침 발음에서 누락이 발생했습니다.",
    "content": "받침을 끝까지 발음하는 연습이 필요합니다.",
    "priority_items": ["받침"]
  },
  "created_at": "2026-07-24T01:00:00Z"
}
```

구현 기준:

- 분석 ID는 UUID 문자열이다.
- IPA는 배열 형식으로 반환한다.
- `operation` 값은 `substitution`, `deletion`, `insertion`, `weakening` 중 하나이다. `weakening`은 정렬상 substitution으로 점수를 계산하되 오류 유형은 약화로 표시한다.
- 점수는 확정된 Levenshtein distance 계산식으로 산출하고 소수점 한 자리로 반환한다.
- `feedback_status`는 `not_requested`, `pending`, `completed`, `failed` 중 하나이다.
- AI 피드백을 아직 생성하지 않았거나 생성에 실패한 경우 `feedback`은 `null`이다.
- 분석이 아직 완료되지 않은 경우 `409 ANALYSIS_IN_PROGRESS`를 반환한다.
- 분석이 실패한 경우 `409 ANALYSIS_FAILED`를 반환한다.
- 저장에 동의하지 않은 분석 결과는 완료 후 30분 동안만 조회할 수 있다.

변경점: 기존 명세의 정수형 분석 ID를 UUID 문자열로 변경하고, 기록 상세 API와 중복되지 않도록 대표 결과 조회 API로 정리했다.

### 분석 결과 삭제

`DELETE /api/v1/analyses/{analysis_id}`

인증이 필요하며 요청 본문은 사용하지 않는다.

응답:

```http
204 No Content
```

구현 기준:

- 본인의 분석 결과만 삭제할 수 있다.
- 분석 결과를 삭제하면 연결된 오류 목록과 교정 피드백도 함께 삭제한다.
- 처리 중인 분석은 삭제할 수 없으며 `409 ANALYSIS_IN_PROGRESS`를 반환한다.
- 존재하지 않거나 다른 사용자의 분석 ID는 `404 ANALYSIS_NOT_FOUND`를 반환한다.

변경점: 저장된 분석 결과를 사용자가 직접 삭제할 수 있도록 삭제 API를 추가했다.

## 11. AI 교정 피드백 생성

`POST /api/v1/analyses/{analysis_id}/feedback`

인증이 필요하며 요청 본문은 사용하지 않는다. 프론트엔드는 외부 AI 서비스가
아니라 이 API만 호출하고, AI 서비스 키와 모델 설정은 백엔드에서 관리한다.

최초 요청 응답:

```json
{
  "analysis_id": "9f6d6c5e-33c4-4c83-989d-67b828ca4f6f",
  "feedback_status": "pending",
  "result_url": "/api/v1/analyses/9f6d6c5e-33c4-4c83-989d-67b828ca4f6f"
}
```

- 피드백 생성 작업을 정상적으로 등록하면 HTTP `202 Accepted`를 반환한다.
- 같은 분석에 대한 작업이 이미 진행 중이면 새 AI 요청을 만들지 않고 동일한
  `202 Accepted` 응답을 반환한다.

이미 생성된 경우 응답:

```json
{
  "analysis_id": "9f6d6c5e-33c4-4c83-989d-67b828ca4f6f",
  "feedback_status": "completed",
  "feedback": {
    "summary": "받침 발음에서 누락이 발생했습니다.",
    "content": "받침을 끝까지 발음하는 연습이 필요합니다.",
    "priority_items": ["받침"]
  }
}
```

- 이미 검증된 피드백이 있으면 AI를 다시 호출하지 않고 HTTP `200 OK`와 기존
  결과를 반환한다.

피드백 결과 확인:

- 별도의 피드백 상태 조회 API는 만들지 않는다.
- 응답의 `result_url`, 즉 `GET /api/v1/analyses/{analysis_id}`를 2초 간격으로
  조회한다.
- `feedback_status`가 `completed` 또는 `failed`가 되면 polling을 중단한다.
- `failed`가 된 뒤 같은 `POST` 요청을 보내면 생성을 다시 시도할 수 있다.

AI 입력 범위:

- 연습 문장, 목표 IPA, 인식 IPA, 점수, 탐지된 발음 오류만 AI에 전달한다.
- 사용자 이메일, 사용자 이름, JWT, 음성 원본과 내부 DB 식별자는 전달하지 않는다.
- 프론트엔드에서 임의 프롬프트나 자유 입력 문장을 받지 않는다.
- AI 피드백은 설명과 연습 방법만 생성하며, 분석 점수와 오류 판정 결과를
  수정하지 않는다.

백엔드 처리 기준:

- 분석 상태가 `completed`인 본인 분석에 대해서만 요청할 수 있다.
- 피드백 생성은 Celery 비동기 작업으로 처리하며 API 요청에서 AI 응답을 직접
  기다리지 않는다.
- 분석별 피드백은 하나만 저장하고, 동시에 여러 요청이 와도 AI 호출은 한 번만
  수행한다.
- AI 응답은 `summary`, `content`, `priority_items` 구조로 파싱하고 필수 필드,
  자료형과 최대 길이를 검증한다. `summary`는 500자 이하, `content`는 2,000자
  이하, `priority_items`는 최대 3개이며 각 항목은 50자 이하 문자열로 제한한다.
- 검증을 통과한 응답만 저장하며 `is_validated=true`로 기록한다.
- AI 제공자에 대한 단일 요청 제한 시간은 30초로 한다.
- AI 제공자 오류나 응답 형식 오류는 최대 2회까지 재시도한다. 모두 실패하면
  `feedback_status=failed`로 처리하되 기존 분석 결과는 그대로 조회할 수 있다.
- 사용자별 요청은 1분에 5회, 분석별 생성 시도는 최초 요청을 포함해 최대
  3회로 제한한다.
- `consent_to_store=false`인 분석의 피드백은 해당 분석의 30분 보관 기간을
  그대로 따르며 별도로 장기 저장하지 않는다.
- 서버 로그에는 AI 서비스 키, 전체 프롬프트와 사용자 식별 정보를 남기지 않는다.

오류 처리:

- 분석이 진행 중이면 `409 ANALYSIS_IN_PROGRESS`를 반환한다.
- 분석이 실패한 상태이면 `409 ANALYSIS_FAILED`를 반환한다.
- 존재하지 않거나 다른 사용자의 분석이면 `404 ANALYSIS_NOT_FOUND`를 반환한다.
- 분석별 최대 생성 횟수를 초과하면 `429 FEEDBACK_RETRY_LIMIT_EXCEEDED`를
  반환한다.
- 피드백 작업을 등록할 수 없으면 `503 FEEDBACK_QUEUE_UNAVAILABLE`을 반환한다.

변경점: 분석 결과에 포함될 AI 교정 설명을 백엔드에서 안전하게 생성할 수 있도록
비동기 피드백 생성 API와 중복 호출, 재시도, 개인정보 전달 범위를 새로 확정했다.

## 12. 학습 기록 목록 조회

`GET /api/v1/records`

인증이 필요하다.

쿼리 파라미터:

- `category`: 카테고리 코드
- `difficulty`: `easy`, `normal`, `hard`
- `page`: 페이지 번호
- `page_size`: 페이지 크기

응답:

```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "analysis_id": "9f6d6c5e-33c4-4c83-989d-67b828ca4f6f",
      "sentence": "안녕하세요.",
      "score": 82.5,
      "difficulty": "easy",
      "category": {
        "code": "batchim",
        "name": "받침"
      },
      "error_count": 1,
      "created_at": "2026-07-24T01:00:00Z"
    }
  ]
}
```

구현 기준:

- 본인의 기록만 조회한다.
- `completed` 상태인 분석만 포함한다.
- `consent_to_store`가 `true`인 분석만 포함한다.
- 최신순으로 정렬한다.
- `page_size`는 1 이상 100 이하이며 생략하면 20으로 처리한다.

변경점: 기존 명세의 기록 목록은 유지하되, 저장 동의와 완료 상태 조건을 명확히 추가했다.

## 13. 학습 기록 상세 조회

별도 API로 구현하지 않는다.

기록 상세 조회는 다음 API를 사용한다.

`GET /api/v1/analyses/{analysis_id}`

구현 기준:

- 기록 상세와 분석 결과 조회는 같은 데이터를 사용하므로 하나의 API로 통합한다.

변경점: 기존 명세에는 기록 상세 API가 따로 있었지만 분석 결과 조회와 거의 같아서 중복 API를 제거했다.

## 14. 통계 요약 조회

`GET /api/v1/statistics/summary`

인증이 필요하다.

응답:

```json
{
  "total_analyses": 12,
  "average_score": 78.4,
  "best_score": 92.0,
  "recent_scores": [
    {
      "analysis_id": "9f6d6c5e-33c4-4c83-989d-67b828ca4f6f",
      "score": 82.5,
      "created_at": "2026-07-24T01:00:00Z"
    }
  ],
  "error_summary": [
    {
      "category": {
        "code": "batchim",
        "name": "받침"
      },
      "count": 5
    }
  ]
}
```

구현 기준:

- `completed` 상태이면서 `consent_to_store`가 `true`인 분석만 통계에 포함한다.
- 평균 점수는 소수점 한 자리까지 반환한다.
- 최근 점수는 최근 완료된 분석 7개를 기준으로 한다.
- 오류 요약은 카테고리별 오류 개수로 계산한다.

변경점: 기존 명세의 통계 API에 저장 동의 조건과 계산 기준을 추가했다.

## 15. 내 정보 조회

`GET /api/v1/users/me`

인증이 필요하다.

응답:

```json
{
  "id": 1,
  "username": "user1",
  "email": "user@example.com",
  "joined_at": "2026-07-24T01:00:00Z",
  "total_completed_analyses": 12
}
```

구현 기준:

- JWT의 사용자 정보를 기준으로 조회한다.
- 저장에 동의한 완료 분석 개수를 함께 반환한다.

변경점: 기존 명세의 사용자 정보 조회는 유지하되, JWT 인증 기준으로 동작하도록 명확히 했다.

## 16. 공통 에러 코드

| HTTP Status | Code | 설명 |
|---|---|---|
| 400 | `INVALID_REQUEST` | 요청 형식 오류 |
| 400 | `AUDIO_FILE_REQUIRED` | 음성 파일 누락 |
| 400 | `INVALID_AUDIO_FORMAT` | 지원하지 않는 음성 파일 형식 |
| 400 | `AUDIO_TOO_LARGE` | 음성 파일 크기 초과 |
| 400 | `AUDIO_TOO_LONG` | 음성 길이 초과 |
| 400 | `INVALID_PAGE` | 페이지 또는 페이지 크기 오류 |
| 401 | `AUTHENTICATION_REQUIRED` | 인증 필요 |
| 401 | `INVALID_TOKEN` | 토큰 오류 |
| 401 | `INVALID_CREDENTIALS` | 로그인 실패 |
| 403 | `PERMISSION_DENIED` | 요청 권한 없음 |
| 404 | `NOT_FOUND` | 요청한 리소스 없음 |
| 404 | `SENTENCE_NOT_FOUND` | 문장 없음 |
| 404 | `ANALYSIS_NOT_FOUND` | 분석 없음 |
| 405 | `METHOD_NOT_ALLOWED` | 지원하지 않는 HTTP 메서드 |
| 409 | `EMAIL_ALREADY_EXISTS` | 이메일 중복 |
| 409 | `SENTENCE_IPA_NOT_READY` | 문장의 목표 IPA가 준비되지 않음 |
| 409 | `ANALYSIS_IN_PROGRESS` | 분석 진행 중 |
| 409 | `ANALYSIS_FAILED` | 분석 실패 |
| 429 | `TOO_MANY_REQUESTS` | 요청 횟수 초과 |
| 429 | `FEEDBACK_RETRY_LIMIT_EXCEEDED` | 분석별 AI 피드백 생성 횟수 초과 |
| 503 | `ANALYSIS_QUEUE_UNAVAILABLE` | 분석 작업 큐 연결 실패 |
| 503 | `FEEDBACK_QUEUE_UNAVAILABLE` | AI 피드백 작업 등록 실패 |
| 500 | `INTERNAL_SERVER_ERROR` | 서버 내부 오류 |

구현 기준:

- 다른 사용자의 분석 ID에 접근한 경우 권한 오류 대신 `404 ANALYSIS_NOT_FOUND`를 반환한다.
- 로그인 실패는 이메일 존재 여부를 알 수 없도록 `INVALID_CREDENTIALS`로 통일한다.

변경점: 기존 명세의 에러 응답을 공통 형식과 코드표로 정리했다.

## 프론트엔드 기본 흐름

1. 회원가입 또는 로그인으로 JWT를 발급받는다.
2. 연습 문장 목록 또는 추천 문장을 조회한다.
3. 사용자가 문장을 선택하고 음성을 업로드한다.
4. 분석 ID를 받은 뒤 상태 조회 API를 polling한다.
5. 상태가 `completed`가 되면 분석 결과를 조회한다.
6. AI 교정 설명이 필요하면 피드백 생성 API를 한 번 호출한다.
7. 분석 결과 조회 API에서 `feedback_status`가 `completed`가 될 때까지 polling한다.
8. 사용자는 기록 목록, 분석 결과, 통계 요약을 확인한다.

## 프론트엔드 연동 참고

- 개발 중 API 문서는 `/api/docs/`, OpenAPI 스키마는 `/api/schema/`에서 확인한다.
- 회원가입, 로그인, 토큰 갱신, 문장 목록 및 문장 상세를 제외한 API 요청에는 `Authorization: Bearer {access_token}`을 보낸다.
- Access Token이 만료되어 `401 INVALID_TOKEN`을 받으면 Refresh Token으로 갱신을 한 번만 시도한다. 갱신도 실패하면 저장된 토큰을 제거하고 로그인 화면으로 이동한다.
- 여러 요청이 동시에 `401`을 받아도 토큰 갱신 요청은 한 번만 보내고, 나머지 요청은 갱신 결과를 기다렸다가 재시도한다.
- Access Token과 Refresh Token을 화면, 로그, 오류 수집 도구에 출력하지 않는다.
- 분석 상태는 2초 간격으로 조회하고 `completed` 또는 `failed`가 되면 polling을 중단한다. 120초가 지나도 완료되지 않으면 사용자에게 지연 상태를 안내하되 서버의 분석 작업을 임의로 실패 처리하지 않는다.
- AI 피드백 생성 요청은 분석 상태가 `completed`가 된 뒤 한 번만 전송한다. `feedback_status=pending`이면 결과 조회 API를 2초 간격으로 확인하고 중복 생성 요청을 보내지 않는다.
- `feedback_status=failed`여도 점수와 오류 목록은 정상 결과로 표시하며, 사용자가 다시 시도할 때만 피드백 생성 API를 재호출한다.
- `consent_to_store=false`인 결과는 완료 후 30분 동안만 조회할 수 있다. 해당 결과에는 만료 안내를 표시하고 기록 및 통계 화면에 노출하지 않는다.
- 날짜는 UTC ISO 8601 형식으로 전달되므로 화면에서는 사용자 기기의 현지 시간으로 변환한다.
- `next`와 `previous`는 Base URL 뒤에 붙여 호출할 수 있는 상대 경로로 전달한다.
- 음성 업로드는 `multipart/form-data`로 보내며 필드 이름은 `sentence_id`, `audio`, `consent_to_store`를 사용한다. 파일명만 바꾸지 말고 실제 녹음 형식을 `wav`, `m4a`, `aac` 중 하나로 맞춘다.
- 에러 메시지만 비교하지 말고 공통 에러 응답의 `error.code`를 기준으로 화면 동작을 분기한다.

## 백엔드 구현 상태

- [x] Custom User, 이메일 고유값 및 `AUTH_USER_MODEL` 설정
- [x] SimpleJWT 30분/7일 정책, 토큰 회전 및 블랙리스트 설정
- [x] Celery와 Redis 연결 및 작업 송수신 검증
- [x] `processing` 상태와 UUID 분석 ID 적용
- [x] IPA 필드 3개를 `JSONField` 음소 배열로 변경
- [x] `consent_to_store=false` 기본값과 미동의 분석 임시 저장 구조 적용
- [x] 미동의 만료 결과 삭제 Celery 작업 구현
- [x] 발음 카테고리 6개 fixture 적용
- [x] 연습 문장과 카테고리 Django 관리자 페이지 등록
- [x] 공통 페이지네이션, 에러 응답, CORS 및 OpenAPI 환경 구성
- [x] 회원가입, 로그인, 토큰 갱신 및 로그아웃 API 구현
- [x] 문장 목록, 상세 및 추천 API 구현
- [x] 음성 파일 형식·크기·길이 검사와 분석 요청 API 구현
- [x] 분석 상태, 결과 조회 및 삭제 API 구현
- [x] 기록 및 통계 API 구현
- [ ] 실제 음성 분석 모듈 연결
- [ ] AI 교정 피드백 생성 API 및 LLM 모듈 연결
