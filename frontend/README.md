# Jipangi Frontend

Expo와 React Native로 구현한 Jipangi 프론트엔드입니다. Node.js 20 이상이
필요합니다.

```bash
cp .env.example .env
npm ci
npm run web
```

`EXPO_PUBLIC_API_BASE_URL`은 실행 환경에 맞게 지정합니다.

- 웹 및 iOS Simulator: `http://127.0.0.1:8000/api/v1`
- Android Emulator: `http://10.0.2.2:8000/api/v1`
- 실제 휴대전화: `http://개발-PC의-LAN-IP:8000/api/v1`

JWT 처리, 화면별 API, 음성 업로드 및 분석 polling은
[API_INTEGRATION.md](API_INTEGRATION.md)를 참고합니다.
