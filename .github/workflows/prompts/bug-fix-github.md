---
description: Fix issues identified by code-review or bug report (GitHub Actions)
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git:*)
  - Bash(gh:*)
  - TodoWrite
model: sonnet
---

# Bug Fix: Apply Corrections

## GitHub Context

- **Repository**: $REPOSITORY
- **Issue Number**: $ISSUE_NUMBER
- **Issue Title**: $ISSUE_TITLE
- **Triggered By**: $TRIGGERED_BY
- **Branch Name**: $BRANCH_NAME

## Configuration

CREATE_BRANCH=$CREATE_BRANCH
CREATE_PR=$CREATE_PR
COMMENT_ON_ISSUE=$COMMENT_ON_ISSUE

## Issue Description

$ISSUE_BODY

## Objective

Analyse the bug report, identify root cause, apply fix, and create PR.
Track progress with TodoWrite and verify fixes with validation tools.

---

## Phase 1: Load Context

### Step 1: Read project standards

```text
Read("CLAUDE.md")
Read("README.md")
```

Extract:

- Validation commands (e.g., `make check && make test`)
- Code style requirements
- Testing approach

### Step 2: Analyse the bug

From the issue description, extract:

- **Symptom**: What is happening that shouldn't?
- **Expected behaviour**: What should happen instead?
- **Reproduction steps**: How to trigger the bug?
- **Affected component**: Which part of the codebase?

### Step 3: Search codebase

```bash
# Search for components mentioned in issue
# Find related functions, classes, modules
git log -10 --oneline -- [relevant-paths]
```

---

## Phase 2: Root Cause Analysis

### Step 1: Investigate

Analyse the code to determine:

- What is the actual bug?
- Why is it happening?
- What was the original intent?
- Is this a logic error, edge case, or missing validation?

### Step 2: Create RCA Document

Save analysis to: `docs/rca/issue-$ISSUE_NUMBER.md`

```markdown
# Root Cause Analysis: Issue #$ISSUE_NUMBER

## Issue Summary

- **Issue**: #$ISSUE_NUMBER - $ISSUE_TITLE
- **URL**: https://github.com/$REPOSITORY/issues/$ISSUE_NUMBER
- **Severity**: [Critical/High/Medium/Low]

## Problem Description

[Clear description from issue]

**Expected**: [What should happen]
**Actual**: [What happens]

## Reproduction

1. [Step 1]
2. [Step 2]
3. [Observe issue]

## Root Cause

### Affected Files

- `path/to/file.py:42` - [Why affected]

### Analysis

[Detailed explanation of root cause]

## Proposed Fix

### Strategy

[High-level approach]

### Changes Required

1. **`path/to/file.py`**: [What to change]

### Testing Requirements

1. Test that fix resolves the issue
2. Test edge cases
3. Regression tests

### Validation Commands

```bash
make check && make test
```
```

---

## Phase 3: Create Fix Plan with TodoWrite

Add each fix step as a todo item:

```text
TodoWrite([
  { content: "Fix root cause in file.py:42", status: "pending", activeForm: "Fixing root cause" },
  { content: "Add regression test", status: "pending", activeForm: "Adding regression test" },
  { content: "Run validation commands", status: "pending", activeForm: "Running validation" },
  ...
])
```

Order todos by dependency (fix first, tests second, validation last).

---

## Phase 4: Apply Fixes

For each issue in the fix plan:

### Step 1: Mark todo as in progress

### Step 2: Read the target file

Understand the full context around the issue, not just the flagged line.

### Step 3: Apply the fix

- **Verify the fix is correct** — review suggestions may need adaptation
- **Preserve existing functionality** — fix the issue without breaking other code
- **Follow codebase conventions** — match style from CLAUDE.md
- **Handle edge cases** — the fix should be complete, not partial

### Step 4: Mark todo as complete

### Step 5: Move to next issue

---

## Phase 5: Validation

After all fixes are applied:

### Step 1: Run validation tools

Execute the validation commands from CLAUDE.md:

```bash
make check
make test
```

### Step 2: Check for regressions

```bash
git diff --stat
```

Review changes to ensure:

- Only intended files were modified
- No unrelated changes introduced
- Fix doesn't break other functionality

---

## Phase 6: GitHub Integration

### Configure Git

```bash
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
```

### Branch Management

**If CREATE_BRANCH = "true":**

```bash
git checkout -b $BRANCH_NAME
```

### Commit Changes

```bash
git add .
git commit -m "fix: $ISSUE_TITLE

Root cause: [one-line from RCA]
Solution: [one-line description]

Fixes #$ISSUE_NUMBER"
```

### Push Branch

**If CREATE_BRANCH = "true":**

```bash
git push origin $BRANCH_NAME
```

### Create Pull Request

**If CREATE_PR = "true":**

```bash
gh pr create \
  --title "fix: $ISSUE_TITLE" \
  --body "$(cat <<EOF
## Summary

Fixes #$ISSUE_NUMBER

## Root Cause

[From RCA document]

## Changes

- \`path/to/file.py\`: [What changed]

## Testing

- ✅ Regression test added
- ✅ All tests passing
- ✅ Validation commands pass

## RCA Document

See \`docs/rca/issue-$ISSUE_NUMBER.md\`

---

Closes #$ISSUE_NUMBER
EOF
)" \
  --base main \
  --head $BRANCH_NAME
```

### Comment on Issue

**If COMMENT_ON_ISSUE = "true":**

```bash
gh issue comment $ISSUE_NUMBER --body "$(cat <<EOF
## Fix Submitted

✅ Fix implemented and tested.

**Branch**: \`$BRANCH_NAME\`
**Root Cause**: [One-line summary]
**RCA Document**: \`docs/rca/issue-$ISSUE_NUMBER.md\`

### Validation

- \`make check\` ✅
- \`make test\` ✅
EOF
)"
```

---

## Phase 7: Report

Generate a fix summary:

```markdown
# Bug Fix Report

**Issue:** #$ISSUE_NUMBER - $ISSUE_TITLE
**RCA Document:** docs/rca/issue-$ISSUE_NUMBER.md
**Scope:** [scope]
**Timestamp:** YYYY-MM-DD HH:MM:SS

---

## Issues Fixed

| File | Change | Status |
|------|--------|--------|
| path/to/file.py:42 | [description] | ✅ Fixed |

## Validation Results

- `make check` — ✅ Passed
- `make test` — ✅ Passed

## Files Modified

- `path/to/file.py` — X changes
- `tests/test_file.py` — regression test added

## Next Steps

- PR created: #[PR_NUMBER]
- Ready for review
```

---

## Important Notes

- **One fix at a time** — Apply and verify each fix before moving to the next
- **Preserve behaviour** — Fixes should not change intended functionality
- **Verify suggestions** — Review recommendations may need adaptation to context
- **Track progress** — Use TodoWrite to maintain visibility into fix progress
- **Run validation** — Always run project validation after fixes
- **Document partial fixes** — If a fix is incomplete, note why in the report
