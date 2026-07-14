# n8n 워크플로우 — 회의록 자동화

`meeting_minutes.json` 을 n8n에 import 해서 사용한다.

## 흐름

```
폴더 감시(/data/inbox) 또는 웹훅
   → Config(오디오 경로 파싱 + 보안 프로파일 결정)
   → 전사(transcribe CLI)
   → 회의록 생성(generate CLI)
   → 보안등급 분기(IF: secure | internal)
        ├─ secure   → /data/out/secure 로 배포
        └─ internal → /data/out/internal 로 배포 → 완료 알림
   (실패 시) 에러 트리거 → 실패 알림 (+ 각 Execute Command 노드는 3회 재시도)
```

## 보안등급 분기 규칙

- 오디오 파일 경로/이름에 **`secure`** 가 포함 → `profile=secure` → **Ollama(로컬) LLM**, 결과는 `out/secure`
- 그 외 → `profile=internal` → **Gemini(클라우드) LLM**, 결과는 `out/internal`

> 예: `./data/inbox/secure_20260714_관제사업.m4a` → 민감 회의로 처리(로컬 LLM, 외부 유출 없음).

## import 방법

1. `docker compose up -d --build` 로 n8n 기동 (http://localhost:5678)
2. n8n UI → **Workflows → Import from File** → `workflows/meeting_minutes.json`
3. (권장) **Settings → Error Workflow** 를 이 워크플로우로 지정하면 "에러 트리거" 노드가 동작한다.
4. 워크플로우 **Activate**.
5. 회의 오디오를 `./data/inbox/` 에 넣으면 자동 처리 → `./data/out/{secure,internal}/`.

## 참고

- 각 단계는 `python -m minutes.transcribe` / `python -m minutes.generate` **CLI를 호출만** 한다.
  (n8n은 오케스트레이션 전담, 로직은 CLI가 단일 진실원천)
- 실패 알림은 `ALERT_WEBHOOK_URL`(.env) 로 POST 한다. 없으면 no-op URL로 빠진다.
- 경량 n8n 이미지는 전사에 Groq 폴백을 사용한다. 로컬 faster-whisper/pyannote가
  필요하면 `docker/Dockerfile.n8n` 을 `--build-arg INSTALL_TRANSCRIBE=1` 로 빌드하고
  `ASR_ENGINE=faster-whisper` 로 설정한다(air-gapped/secure 환경).
