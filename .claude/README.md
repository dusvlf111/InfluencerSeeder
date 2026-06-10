# .claude 워크플로우 설정

InfluencerSeeder(PyQt6 + Selenium + CSV) 프로젝트용 PRD → Task → 실행 파이프라인.
레퍼런스([claude-setting-v0.1](https://github.com/dusvlf111/claude-setting-v0.1-fsd-next-etc))를
이 프로젝트(Python/pytest) 스택에 맞게 적응시킨 구성.

## 파이프라인

```
/prd-maker   기능 메모/아이디어 → 구조화된 PRD (.claude/tasks/prd-*.md)
     ↓
/task-maker  PRD → Push 단위 작업 파일 (.claude/tasks/todo/tasks-*-pushN.md)
     ↓
/task-runner todo/ 작업을 task-executor 에이전트에 위임 → 구현·테스트·커밋
     ↓
/task-cleaner 완료된 PRD/task/스크린샷을 done/{기능명}/ 으로 아카이브
```

## 구성 요소

### 스킬 (`skills/`) — `/이름` 으로 호출
| 스킬 | 역할 |
|------|------|
| `prd-maker` | 요구사항 메모를 이 프로젝트 포맷의 PRD로 작성 |
| `task-maker` | PRD를 Push 단위 + 커밋 단위 작업으로 분해 (컨벤션·문서·이미지 경로를 task에 임베딩) |
| `task-runner` | todo/ 작업을 task-executor에 위임하는 오케스트레이터 |
| `task-cleaner` | 완료 작업 아카이브 |

### 에이전트 (`agents/`)
| 에이전트 | 모델 | 역할 |
|----------|------|------|
| `task-executor` | inherit | 자율 구현·pytest 작성/실행·커밋·오류수정 (Skill 도구 없음) |
| `test-runner` | haiku | 변경분 pytest 검증, 간단한 오류 직접 수정 |

### 훅 (`hooks/`) + `settings.json`
| 훅 | 트리거 | 역할 |
|----|--------|------|
| `post-edit-format.sh` | PostToolUse(Edit/Write) | .py 파일 ruff/black 자동 포맷 (없으면 no-op) |
| `check-tasks.sh` | Stop | `.task-running` 있을 때 미완료 작업 남으면 계속 진행 강제 |
| `inject-task-context.sh` | SessionStart(compact) | 컴팩션 후 진행 중 task 상태 재주입 |

> 훅은 `jq` 없이 `python3` 폴백으로 JSON을 파싱한다 (이 환경엔 jq 미설치).

## 핵심 설계 원칙

- **task-executor는 Skill/Agent 도구가 없다.** 그래서 `task-maker`가 작업 파일에
  프로젝트 컨벤션(신호/슬롯·디자인토큰·스토리지·테스트 격리)을 **요약 임베딩**하고
  참조 문서·이미지의 **경로를 명시**한다. 에이전트는 Read로 직접 읽는다.
- **이 프로젝트는 Python/PyQt6 + pytest.** 레퍼런스의 React/Vercel/FSD 규칙은 제거됨.
- 테스트는 `cd src && .venv/bin/pytest tests/ -v`. 외부 의존성(Selenium/네트워크)은 전부 mock.

## 사용 예

```
/prd-maker .claude/tasks/prd-260610-3.md   # 메모를 PRD로 구체화
/task-maker .claude/tasks/prd-260610-3.md  # PRD를 작업으로 분해
/task-runner                               # todo/ 작업 자동 실행
/task-cleaner stealth-resume-v3            # 완료 후 정리
```
