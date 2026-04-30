# Claude Code WIP Tracking

Track in-session work progress using Claude Code's built-in TodoWrite/TaskCreate tools.

## Tool Selection

| Tool | When | Features |
|------|------|----------|
| **TaskCreate** | Multiple independent tasks, dependency management needed | ID-based, status tracking, blockedBy |
| **TodoWrite** | Sequential step list | Simple, ordered progression |

### Decision Tree

```
New work arrives
  ├─ Multiple independent tasks → TaskCreate
  │   (e.g., "modify 3 files in parallel")
  └─ Sequential steps → TodoWrite
      (e.g., "5-step deploy procedure")
```

## Compact 후 작업 복원

Compact(컨텍스트 압축) 발생 시 기존 진행 중이던 작업 목록이 사라질 수 있다. 복원 절차:

### 감지

Compact 후 세션 재개 시 (summary가 포함된 시스템 메시지 확인), 이전 작업 상태를 복원해야 한다.

### 절차

1. **이전 작업 요약 출력**: Compact summary에서 진행 중이던 작업/태스크를 추출하여 사용자에게 표시
2. **AskUserQuestion(multiSelect)으로 복원 대상 선택**: 이전 작업 목록을 선택지로 제시하여 어떤 작업을 이어갈지 확인
3. **TodoWrite로 재등록**: 사용자가 선택한 항목만 TodoWrite로 재등록 (이전 상태 유지: completed는 completed, pending은 pending)

### 예시

```
# 1. 요약 출력
"compact 전 진행 중이던 작업:"
- [x] API 엔드포인트 구현
- [/] 테스트 작성
- [ ] PR 생성

# 2. AskUserQuestion (multiSelect: true)
"이어서 진행할 작업을 선택하세요"
→ 사용자 선택: 테스트 작성, PR 생성

# 3. 선택된 항목만 TodoWrite 재등록
TodoWrite([
  { content: "테스트 작성", status: "in_progress" },
  { content: "PR 생성", status: "pending" }
])
```

### 스킵 조건

- Compact summary에 진행 중 작업이 없으면 스킵
- 사용자가 "새로 시작"을 선택하면 스킵

## TodoWrite Pattern

### Register

```
Before starting:
TodoWrite([
  { content: "Step 1 description", status: "in_progress" },
  { content: "Step 2 description", status: "pending" },
  { content: "Step 3 description", status: "pending" }
])
```

### Progress

```
After step 1 completes:
TodoWrite([
  { content: "Step 1 description", status: "completed" },
  { content: "Step 2 description", status: "in_progress" },
  { content: "Step 3 description", status: "pending" }
])
```

## TaskCreate Pattern

### Register

```
TaskCreate({ subject: "Modify file A", status: "pending" })
TaskCreate({ subject: "Modify file B", status: "pending" })
TaskCreate({ subject: "Run tests", status: "pending", addBlockedBy: ["1", "2"] })
```

### Progress

```
TaskUpdate({ taskId: "1", status: "in_progress" })
// do work
TaskUpdate({ taskId: "1", status: "completed" })
```
