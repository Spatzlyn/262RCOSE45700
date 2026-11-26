# 프론트엔드 · 고연오 · v1.1

- [현재 실행 화면](f3-f5/app.html): F1~F5 실제 API 연결 + **T2 Track 2 영상** ([설명](TRACK2_VIEWER.md), 11/26 백엔드 `/api/track2/*`에 연결). 배포 서버 주소 `http://100.52.183.88:8888`.
- 11/25: v1.1 보조 4개를 F3·F4·F5에 표시, 새 실제 Run `v11_a_e18f74ffcc`·`v11_b_9895a83702`로 F1~F5 확인 (F4 기본 Base = 예측 있는 같은 버전 Run, 형식 오류 원문 표시). 화면만 고친 뒤 `python3 prep.py --html-only`.
- [원본 템플릿](f3-f5/template.html): View 수정은 이 파일부터 진행.
- [단일 파일 미리보기](f3-f5/index.html): 기존 파일 모드; 원본 데이터 사진은 공개 브랜치에서 제외. 실제 사진은 API 모드에서 기존 `IMAGE_ROOT`로 조회.
- [로컬 F1~F5 검증 기록](../browser_verification.json) 및 [검증 스크립트](../check_f1_f5.mjs).
- [기존 11/13 작업 설명](FRONTEND_1113.md) · [이전 용어 및 해외 벤치마크](../docs/mentoring/1120-terminology-and-benchmarks.md).

API를 먼저 켠 뒤 브라우저에서 `app.html` 열기. v1.0은 관계 12칸·이전 관계 표, v1.1은 9칸과 보조 지표·미검수·미추론 표시. 서로 다른 버전은 비교 불가. 로컬 실제 사진 연결을 검증했으나 실제 EC2 배포는 담당자 검토 후 별도 적용.

브라우저 자동 확인을 재실행하려면 저장소 루트에서 `npm install --no-save --no-package-lock playwright`, `npx playwright install chromium` 후 API를 켜고 `node check_f1_f5.mjs` 실행. 필요 시 `TEST_API_URL`과 `CHROMIUM_PATH` 환경 변수 지정. 라벨링 HTML을 로컬 생성한 뒤 `node check_blind_form.mjs`로 독립 양식을 확인할 수 있음.
