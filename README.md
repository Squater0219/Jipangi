# Jipangi

청각장애인을 위한 IPA 기반 발음 교정 서비스 졸업과제입니다. 프론트엔드와
Django 백엔드를 한 저장소에서 관리합니다.

## 저장소 구조

```text
.
├── backend/     # Django REST API, Celery, MySQL 설정
├── frontend/    # 프론트엔드 애플리케이션
├── docs/        # API 명세, OpenAPI 문서, ERD
└── tests/       # Postman 통합 테스트
```

## 백엔드 실행

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
backend/scripts/start_mysql.sh
brew services start redis
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py loaddata initial_categories
../.venv/bin/python manage.py runserver
```

Celery worker는 별도 터미널에서 실행합니다.

```bash
cd backend
../.venv/bin/celery -A config worker --loglevel=INFO
```

API 문서는 서버 실행 후 `http://127.0.0.1:8000/api/docs/`에서 확인할 수
있습니다. 상세 백엔드 설명은 [backend/README.md](backend/README.md), API
명세는 [docs/api-spec-v2.md](docs/api-spec-v2.md)를 참고합니다.

## 프론트엔드

Expo와 React Native로 구현되어 있습니다. Node.js 20 이상을 사용합니다.

```bash
cd frontend
nvm use
npm ci
npm run web
```

API 기본 주소와 플랫폼별 설정은 [frontend/README.md](frontend/README.md)를
참고합니다.

## 전체 API 테스트

Django 서버와 Celery worker가 실행된 상태에서 다음 명령을 사용합니다.

```bash
postman collection run tests/postman/jipangi-api.postman_collection.json \
  -e tests/postman/local.postman_environment.json \
  --bail failure \
  --delay-request 500
```

실제 비밀번호와 서명 키가 담긴 `.env` 파일은 저장소에 올리지 않습니다.
