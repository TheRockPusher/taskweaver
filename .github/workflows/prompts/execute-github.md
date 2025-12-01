---
description: Execute an implementation plan with TodoWrite tracking (GitHub Actions)
allowed-tools:
  - Read
  - Glob
  - Grep
  - Write
  - Edit
  - Bash
  - TodoWrite
  - Task
model: sonnet
---

# Execute: Implement from Plan

## GitHub Context

- **Repository**: $REPOSITORY
- **Triggered By**: $TRIGGERED_BY

## Plan to Execute

Read plan file: `$PLAN_PATH`

---

## Phase 0: Plan Validation

1. Read the ENTIRE plan file
2. Verify these sections exist:
   - CONTEXT REFERENCES (Mandatory Reading)
   - STEP-BY-STEP TASKS
   - VALIDATION COMMANDS
3. If anything is unclear or ambiguous, note it for the report

---

## Phase 1: Context Loading

**Read ALL files listed in "Mandatory Reading" section before any implementation.**

For each file reference:

- Read the specified line ranges
- Understand the patterns to follow
- Note imports, naming conventions, error handling

This ensures pattern consistency across implementation.

---

## Phase 2: TodoWrite Setup

**Populate TodoWrite from "STEP-BY-STEP TASKS" section:**

Extract each task and create todo items:

```text
Example plan tasks:
### CREATE src/services/auth.py
### UPDATE src/routes/api.py
### ADD tests/test_auth.py

Becomes TodoWrite:
1. Create src/services/auth.py
2. Update src/routes/api.py
3. Add tests/test_auth.py
4. Run validation commands
```

Mark first task as `in_progress` before starting.

---

## Phase 3: Execute Tasks

For EACH task in order:

### a. Read context

- Re-read pattern references from plan
- Read existing files if modifying

### b. Implement

- Follow specifications exactly
- Mirror patterns from mandatory reading
- Maintain consistency with codebase

### c. Verify and update

- Check syntax after changes
- Mark task `completed` in TodoWrite
- Mark next task `in_progress`

---

## Phase 4: Testing

After implementation tasks:

- Create test files from plan
- Implement all specified test cases
- Run tests, fix failures before proceeding

---

## Phase 5: Validation

Execute ALL validation commands from plan:

```bash
# Level 1: Lint/format
# Level 2: Type check
# Level 3: Unit tests
# Level 4: Integration tests
```

If any fails: fix → re-run → continue only when passing.

---

## Phase 6: Completion Report

### Summary

- Tasks completed (from TodoWrite)
- Files created/modified

### Validation Results

- All command outputs (pass/fail)

### Next Steps

- Ready for commit
- Any deviations or issues encountered

---

## Guidelines

- **Doubts?** Note them in the report
- **Deviations?** Explain why in report
- **Failures?** Fix before marking complete
- **Never skip** validation commands
