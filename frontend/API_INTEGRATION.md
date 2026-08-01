# 프론트엔드 API 연동 가이드

이 문서는 Jipangi 프론트엔드에서 Django API를 사용할 때 필요한 내용을 정리한
문서입니다. 전체 요청과 응답 예시는 [`../docs/api-spec-v2.md`](../docs/api-spec-v2.md),
Swagger UI는 백엔드 실행 후 `http://127.0.0.1:8000/api/docs/`에서 확인할 수
있습니다.

## 1. 개발 환경 실행

Node.js 20 이상을 사용합니다. 저장소의 `frontend/.nvmrc`가 버전을 지정합니다.

```bash
cd frontend
nvm use
cp .env.example .env
npm ci
npm run web
```

웹 개발 서버는 기본적으로 `http://localhost:8081`에서 실행됩니다. Django와
Celery도 별도 터미널에서 실행해야 음성 분석까지 확인할 수 있습니다.

```bash
# 터미널 1
cd backend
../.venv/bin/python manage.py runserver

# 터미널 2
cd backend
../.venv/bin/celery -A config worker --loglevel=INFO
```

API 주소는 `EXPO_PUBLIC_API_BASE_URL`로 설정합니다.

| 실행 환경 | API 주소 |
|---|---|
| 웹, iOS Simulator | `http://127.0.0.1:8000/api/v1` |
| Android Emulator | `http://10.0.2.2:8000/api/v1` |
| 실제 휴대전화 | `http://개발-PC의-LAN-IP:8000/api/v1` |

API 경로 끝에는 `/`를 붙이지 않습니다. 예를 들어 문장 목록은
`/sentences/`가 아니라 `/sentences`입니다.

## 2. 인증 처리

로그인은 `POST /auth/login`으로 요청합니다.

```json
{
  "email": "user@example.com",
  "password": "password1234"
}
```

응답의 토큰 필드 이름은 `access_token`, `refresh_token`입니다. 인증이 필요한
요청에는 다음 헤더를 보냅니다.

```http
Authorization: Bearer {access_token}
```

Access Token 요청이 `401`로 실패하면 `POST /auth/token/refresh`에 현재
`refresh_token`을 보내고, 응답으로 받은 Access/Refresh Token을 모두 교체합니다.
여러 요청이 동시에 실패해도 갱신 요청은 한 번만 보내야 합니다. 갱신까지
실패하면 저장된 토큰을 지우고 로그인 화면으로 이동합니다.

로그아웃은 `POST /auth/logout`에 `refresh_token`을 보내야 합니다. 화면에서
토큰만 삭제하면 서버의 Refresh Token은 계속 유효하므로 반드시 로그아웃 API를
먼저 호출합니다.

## 3. 화면별 API

| 화면 또는 기능 | 요청 | 참고 |
|---|---|---|
| 회원가입 | `POST /auth/signup` | 가입 직후 JWT 반환 |
| 로그인 | `POST /auth/login` | 이메일로 로그인 |
| 사용자 정보 | `GET /users/me` | 인증 필요 |
| 문장 목록 | `GET /sentences` | `difficulty`, `category`, `page`, `page_size` 사용 |
| 문장 상세 | `GET /sentences/{id}` | 정답 IPA인 `target_ipa` 포함 |
| 추천 문장 | `GET /sentences/recommendation` | 인증 필요 |
| 분석 요청 | `POST /analyses` | multipart, 인증 필요 |
| 분석 상태 | `GET /analyses/{uuid}/status` | 비동기 작업 상태 확인 |
| 분석 결과 | `GET /analyses/{uuid}` | 완료 후 조회 |
| 분석 삭제 | `DELETE /analyses/{uuid}` | 본인 결과만 삭제 가능 |
| 학습 기록 | `GET /records` | 저장에 동의한 결과만 반환 |
| 통계 | `GET /statistics/summary` | 저장에 동의한 결과만 집계 |

난이도는 `easy`, `normal`, `hard`를 사용합니다. 카테고리 코드는 다음과
같습니다.

| 화면 표시 | API 값 |
|---|---|
| 받침 | `batchim` |
| 연음 | `liaison` |
| 비음화 | `nasalization` |
| 유음화 | `liquidization` |
| 경음화 | `tensification` |
| 구개음화 | `palatalization` |

문장 목록 응답에는 IPA가 없습니다. 사용자가 문장을 선택하면 문장 상세 API를
호출하고 `target_ipa`를 가져와야 합니다. IPA는 문자열 하나가 아니라 음소별
문자열 배열입니다.

```json
["a", "n", "n", "j", "ʌ", "ŋ"]
```

목록형 API는 `count`, `next`, `previous`, `results` 구조로 응답합니다. 실제
목록은 항상 `results`에서 읽습니다.

## 4. 음성 분석 흐름

분석 요청은 JSON이 아니라 `multipart/form-data`로 전송합니다.

| 필드 | 형식 | 설명 |
|---|---|---|
| `sentence_id` | 정수 | 선택한 문장 ID |
| `audio` | 파일 | `wav`, `m4a`, `aac`, `webm` |
| `consent_to_store` | boolean | 기록과 통계 저장 동의 |

Expo 웹은 녹음 결과를 Blob으로 읽고 실제 WebM 파일로 첨부합니다.

```javascript
const blob = await fetch(audioUri).then((response) => response.blob());
formData.append('audio', blob, `pronunciation-${Date.now()}.webm`);
```

분석 요청이 접수되면 HTTP `202`와 UUID 형식의 `analysis_id`가 반환됩니다.
즉시 결과 API를 호출하지 말고 다음 순서로 처리합니다.

1. `POST /analyses`로 분석을 등록합니다.
2. `GET /analyses/{analysis_id}/status`를 2초 간격으로 호출합니다.
3. 상태가 `completed`이면 `GET /analyses/{analysis_id}`로 결과를 받습니다.
4. 상태가 `failed`이면 polling을 중단하고 오류를 표시합니다.
5. 120초 동안 끝나지 않으면 지연 안내를 표시합니다.

상태 값은 `pending`, `processing`, `completed`, `failed`입니다. 결과의 주요
필드는 `target_ipa`, `recognized_ipa`, `score`, `errors`, `feedback`입니다.
오류별 `specific_feedback`에는 `summary`, `content`, `practice_tip`이 들어가며,
생성 전에는 빈 객체입니다.

`consent_to_store=false`인 결과는 서버에서 30분 뒤 삭제되며 기록과 통계에
포함되지 않습니다. 따라서 프론트엔드도 해당 결과를 로컬 학습 기록에 추가하지
않습니다.

## 5. 오류 처리와 현재 제한 사항

백엔드 오류는 다음 공통 형식을 사용합니다. 화면 동작은 번역된 메시지가 아니라
`error.code`를 기준으로 구분합니다.

```json
{
  "error": {
    "code": "INVALID_TOKEN",
    "message": "토큰이 유효하지 않습니다.",
    "details": {}
  }
}
```

- 현재 음성 분석기는 프론트엔드 연동용 개발 구현입니다. 실제 음성을 판정하지
  않고 정답 IPA를 그대로 반환하므로 결과가 100점으로 나옵니다.
- AI 교정 피드백 생성 API는 명세만 확정된 상태입니다. 백엔드 구현 전에는
  피드백 생성 요청과 `feedback_status` polling을 활성화하지 않습니다.
- Access Token과 Refresh Token은 콘솔, 오류 메시지, 화면에 출력하지 않습니다.
- 브라우저에서는 `http://localhost:8081`의 마이크 권한을 허용해야 녹음할 수
  있습니다.

현재 연동 예시는 [`App.js`](App.js)에 구현되어 있습니다. API 계약을 변경할
때는 `docs/api-spec-v2.md`, `docs/openapi.yaml`, 이 문서를 함께 수정합니다.
