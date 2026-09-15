# portfolio-holdings-ocr

증권사/코인 거래소 앱의 보유종목 캡처 이미지를 읽어, 이 저장소의 포트폴리오 앱
(`app/src/main/assets/index.html`) 설정 탭 **"보유 화면 텍스트 붙여넣기"** 에
그대로 붙여넣을 수 있는 텍스트로 변환하는 Claude Code 플러그인입니다.

## 설치 (로컬 테스트)

```bash
claude --plugin-dir ./claude-plugin
```

설치 후 캡처 이미지를 첨부하고 "이 화면 인식해서 텍스트로 뽑아줘" 처럼 요청하면
`holdings-ocr` 스킬이 자동으로 실행됩니다.

## 구성

```
claude-plugin/
├── .claude-plugin/
│   └── plugin.json
└── skills/
    └── holdings-ocr/
        └── SKILL.md
```
