# Postman API 테스트

로컬 서버와 Celery worker를 실행한 뒤 다음 명령으로 전체 API를 테스트합니다.

```bash
postman collection run tests/postman/jipangi-api.postman_collection.json \
  -e tests/postman/local.postman_environment.json \
  --bail failure \
  --delay-request 500
```

컬렉션은 회원가입, JWT 로그인·갱신·로그아웃, 문장 조회, WAV 업로드,
비동기 분석 결과, 학습 기록과 통계, 분석 삭제를 순서대로 검증합니다.
실행할 때마다 `postman-` 접두사의 임시 이메일을 새로 생성합니다.

Postman 계정 로그인 없이도 로컬 실행은 가능합니다. 이 경우 실행 결과를
Postman Cloud에 게시할 수 없다는 안내만 출력됩니다.
