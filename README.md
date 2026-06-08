# 📱 포트폴리오 앱 — APK 빌드 가이드

## 🚀 방법 1: GitHub Actions (가장 쉬움 — 5분)

### 1단계: GitHub 리포 생성
1. https://github.com/new 접속
2. 리포 이름: `portfolio-app`
3. Public 선택 → Create repository

### 2단계: 이 폴더 업로드
```bash
cd portfolio_apk
git init
git add .
git commit -m "첫 커밋"
git branch -M main
git remote add origin https://github.com/YOUR_ID/portfolio-app.git
git push -u origin main
```

### 3단계: APK 다운로드
1. GitHub → Actions 탭 클릭
2. "Build Portfolio APK" 워크플로우 실행 중 확인
3. 완료 후 "Artifacts" 섹션에서 `portfolio-apk` 다운로드
4. 압축 해제 → `.apk` 파일 스마트폰으로 전송

### 스마트폰 설치
- Android: `.apk` 파일 탭 → "알 수 없는 앱" 허용 → 설치
- iOS: APK는 Android 전용 (iOS는 PWA 방식 사용)

---

## 🖥️ 방법 2: 로컬 직접 빌드 (Android Studio 있을 때)

```bash
# Android Studio 설치 후:
./gradlew assembleDebug
# 결과: app/build/outputs/apk/debug/app-debug.apk
```

---

## 앱 기능

| 탭 | 내용 |
|---|---|
| ◎ 홈 | 총 자산, P&L, 자산별 비중 |
| ≡ 종목 | 국내/해외/채권/대체투자 카드 |
| ⊖ 리밸런싱 | 월 투자금 슬라이더 + 배분 가이드 |
| ↗ 분석 | PER 비교 (저평가/고평가 필터) |
| ◈ 설정 | 환율 설정 + 업비트 연동 |

