---
description: Execute an implementation plan with TodoWrite tracking
allowed-tools:
  - Read
  - Glob
  - Grep
  - Write
  - Edit
  - Bash
  - TodoWrite
  - Task
  - AskUserQuestion
argument-hint: <path-to-plan>
model: sonnet
---

# Execute: Implement from Plan

## Plan to Execute

Read plan file: `$ARGUMENTS`

---

## Phase 0: Plan Validation

1. Read the ENTIRE plan file
2. Verify these sections exist (ask user if missing):
   - CONTEXT REFERENCES (Mandatory Reading)
   - STEP-BY-STEP TASKS
   - VALIDATION COMMANDS
3. If anything is unclear or ambiguous, use AskUserQuestion before proceeding

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
- **Run relevant tests for this phase** (catch issues early, not just at end)
- Mark task `completed` in TodoWrite
- Mark next task `in_progress`

### d. Namespace check (when creating new files/exports)

- If creating new module: verify name doesn't match any exported symbol
- If adding export: verify symbol doesn't shadow existing module
- Quick test: `python -c "from package import X; print(type(X))"`

---

## Phase 4: Testing

After implementation tasks:

- Create test files from plan
- Implement all specified test cases
- **Update test fixtures if module structure changed** (e.g., renames, new agents)
- Run tests, fix failures before proceeding

**Test Fixture Checklist** (if refactoring):
- [ ] Fixture imports point to correct modules (check for renamed files)
- [ ] Mock targets reference actual module/class locations
- [ ] Integration fixtures updated for new architecture

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

## Phase 6: Documentation Check

**If implementation changes user-facing behaviour, update existing docs:**

- `README.md` - Usage, setup, features
- `CLAUDE.md` - AI instructions, commands, conventions
- `.agents/PRD.md` - Requirements status, phase completion

Skip if changes are internal-only with no documentation impact.

---

## Phase 7: Completion Report

### Summary

- Tasks completed (from TodoWrite)
- Files created/modified
- Docs updated (if any)

### Validation Results

- All command outputs (pass/fail)

### Next Steps

- Ready for `/commit`

---

## Guidelines

- **Doubts?** Ask user, don't assume
- **Deviations?** Explain why in report
- **Failures?** Fix before marking complete
- **Never skip** validation commands

ultrathink
