---
description: Generate post-implementation report comparing plan vs actual execution
allowed-tools:
  - Read
  - Glob
  - Grep
  - Write
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git status:*)
  - Bash(git show:*)
  - AskUserQuestion
argument-hint: [plan-file] (optional - auto-detects latest)
model: sonnet
---

# Execution Report: Post-Implementation Analysis

## Objective

Generate a structured report comparing what was **planned** versus what was
**actually implemented**, documenting divergences, challenges, and learnings.

**Purpose**: Capture implementation reality to feed into system review for
continuous improvement of the PIV workflow.

---

## Phase 1: Plan File Resolution

### If argument provided

Read plan file: `$ARGUMENTS`

### If no argument (auto-detect)

1. Search for recent plans:

    ```text
    Glob(".agents/plans/*.md")
    ```

2. Sort by modification time (most recent first)

3. Present options to user:

    ```text
    AskUserQuestion:
    "Which plan file should I analyse?"
    Options: [list of 3-4 most recent plans]
    ```

4. Read selected plan file

---

## Phase 2: Gather Implementation Evidence

### Step 1: Extract plan metadata

From the plan file, extract:

- Feature name and description
- Files to create (from "New Files to Create" section)
- Files to modify (from "Mandatory Reading" section)
- Validation commands (from "VALIDATION COMMANDS" section)
- Acceptance criteria (from "ACCEPTANCE CRITERIA" section)

### Step 2: Check git history

Find commits since plan creation:

```bash
git log --oneline --since="[plan file mtime]" --all
git diff --stat HEAD~[n]..HEAD  # Changes in recent commits
```

### Step 3: Verify file changes

For each file mentioned in plan:

- Check if created/modified as expected
- Note any files created that weren't in plan
- Note any planned files that weren't created

### Step 4: Run validation commands

Execute validation commands from plan:

```bash
# Whatever was specified in VALIDATION COMMANDS section
```

Record pass/fail status for each.

---

## Phase 3: Divergence Analysis

For each discrepancy between plan and implementation:

### Classify divergence type

| Type | Description |
|------|-------------|
| **Addition** | Implemented something not in plan |
| **Omission** | Skipped something from plan |
| **Modification** | Changed approach from plan |
| **Substitution** | Replaced planned approach entirely |

### Identify divergence reason

| Reason | Meaning |
|--------|---------|
| **Better approach found** | Discovered superior pattern during implementation |
| **Plan assumption wrong** | Plan assumed something that didn't exist |
| **Security concern** | Original approach had security issues |
| **Performance issue** | Original approach had performance problems |
| **Dependency conflict** | External constraint prevented planned approach |
| **Time constraint** | Simplified to meet deadline |
| **Unclear requirement** | Plan was ambiguous, made judgement call |

---

## Phase 4: Generate Report

Write report to: `.agents/execution-reports/{feature-name}.md`

Use this structure:

````markdown
# Execution Report: {Feature Name}

**Plan file**: {path to plan}
**Date**: {current date}
**Implementation period**: {first commit} to {last commit}

---

## Meta Information

| Metric | Value |
|--------|-------|
| Files added | {count} |
| Files modified | {count} |
| Lines changed | +{added} -{removed} |
| Commits | {count} |
| Plan adherence | {percentage}% |

### Files Added

- `path/to/new/file.py` - {purpose}

### Files Modified

- `path/to/existing/file.py` - {what changed}

---

## Validation Results

| Check | Status | Notes |
|-------|--------|-------|
| Syntax & Linting | ✓/✗ | {details} |
| Type Checking | ✓/✗ | {details} |
| Unit Tests | ✓/✗ | {X passed, Y failed} |
| Integration Tests | ✓/✗ | {X passed, Y failed} |

---

## What Went Well

- {Specific things that worked smoothly}
- {Patterns that proved effective}
- {Tools or approaches that helped}

---

## Challenges Encountered

- **{Challenge title}**: {Description of difficulty and how it was resolved}

---

## Divergences from Plan

### {Divergence 1 Title}

| Aspect | Detail |
|--------|--------|
| **Planned** | {What the plan specified} |
| **Actual** | {What was implemented instead} |
| **Type** | Addition / Omission / Modification / Substitution |
| **Reason** | {Why this divergence occurred} |
| **Impact** | {Effect on feature or codebase} |

{Repeat for each divergence...}

---

## Skipped Items

| Item | Reason | Future Action |
|------|--------|---------------|
| {What was skipped} | {Why} | {Should it be done later?} |

---

## Recommendations

### For Plan Command

- {Suggestions to improve /plan output}

### For Implement Command

- {Suggestions to improve /implement process}

### For CLAUDE.md

- {Patterns or anti-patterns to document}

### For Future Similar Features

- {Learnings applicable to similar work}

---

## Summary

**Overall assessment**: {Brief evaluation of implementation success}

**Ready for**: `/validation:system-review` to extract process improvements
````

---

## Phase 5: Output Summary

After generating the report, display:

1. **Report location**: Full path to generated file
2. **Key metrics**: Files changed, plan adherence percentage
3. **Divergence count**: Number of divergences by type
4. **Validation status**: Pass/fail summary
5. **Next step**: Suggest running `/validation:system-review`

---

## Important Notes

- **Be honest**: Document actual problems, not sanitised versions
- **Be specific**: Include file paths, line numbers, concrete examples
- **Be constructive**: Frame challenges as learning opportunities
- **Be complete**: Capture everything for system review to analyse

ultrathink
