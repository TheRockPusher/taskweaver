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
model: opus
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
- Mark task `completed` in TodoWrite
- Mark next task `in_progress`

---

## Phase 4: Testing

After implementation tasks:

- Create test files from plan
- Implement all specified test cases
- Run tests, fix failures before proceeding

---

## Phase 5: Validation (MANDATORY ITERATION)

**CRITICAL**: This phase MUST complete successfully before finishing.

Execute ALL validation commands from plan in order:

```bash
# Level 1: Lint/format (e.g., ruff check ., npm run lint)
# Level 2: Type check (e.g., mypy ., npx tsc --noEmit)
# Level 3: Unit tests (e.g., pytest, npm test)
# Level 4: Integration tests (e.g., pytest tests/integration/)
# Level 5: Manual validation steps from plan
```

### Validation Iteration Loop

**For EACH validation command:**

1. **Run the command**
   - Execute exactly as specified in plan
   - Capture full output

2. **Check result**
   - ✅ **PASS**: Continue to next validation level
   - ❌ **FAIL**: Enter fix iteration loop

3. **Fix iteration loop (if failed)**
   - Analyze the error output carefully
   - Identify root cause (don't just fix symptoms)
   - Make necessary fixes using Edit tool
   - Re-run the SAME validation command
   - Repeat until PASS

4. **Only proceed when ALL validations pass**

### Validation Failure Handling

**Common failures and fixes:**

- **Linting errors**: Fix code style, imports, unused variables
- **Type errors**: Add/correct type hints, fix type mismatches
- **Test failures**: Fix logic bugs, update tests if requirements changed
- **Integration failures**: Check dependencies, environment, external services

**If stuck after 3 iterations on same error:**

- Use AskUserQuestion to get user guidance
- Document the blocker in completion report
- Do NOT mark implementation as complete

### Validation Success Criteria

Implementation is ONLY complete when:

- [ ] All Level 1-4 validation commands exit with code 0
- [ ] No errors, warnings, or failures in output
- [ ] Manual validation steps (Level 5) documented as passing

**NEVER skip validation or continue with failures.**

---

## Phase 6: Documentation Check

**If implementation changes user-facing behaviour, update existing docs:**

- `README.md` - Usage, setup, features
- `CLAUDE.md` - AI instructions, commands, conventions
- `.agents/PRD.md` - Requirements status, phase completion

Skip if changes are internal-only with no documentation impact.

---

## Phase 7: Completion Report

**Only generate this report after ALL validations pass.**

### Summary

- ✅ Tasks completed (list from TodoWrite)
- 📝 Files created/modified (with line counts)
- 📚 Documentation updated (if any)

### Validation Results

**MUST show all passing:**

```text
✅ Level 1 (Lint/Format): [command] - PASSED
✅ Level 2 (Type Safety): [command] - PASSED
✅ Level 3 (Unit Tests): [command] - PASSED
✅ Level 4 (Integration): [command] - PASSED / N/A
✅ Level 5 (Manual): [steps] - COMPLETED
```

If any validation failed, show:

- ❌ Error output
- 🔧 Fixes applied
- 🔁 Iterations required
- ✅ Final passing status

### Implementation Metrics

- Total tasks: X
- Files changed: Y
- Validation iterations: Z
- Time to passing: N/A (don't estimate)

### Next Steps

- ✅ **Ready for `/commit`** (all validations passed)
- OR
- ❌ **Blocked** (document why, ask user for guidance)

---

## Guidelines

- **Doubts?** Ask user, don't assume
- **Deviations?** Explain why in report
- **Failures?** Fix before marking complete
- **Never skip** validation commands

ultrathink
