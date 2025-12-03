---
description: Analyse execution report to extract process improvements for AI workflow
allowed-tools:
  - Read
  - Glob
  - Grep
  - Write
  - Edit
  - AskUserQuestion
argument-hint: [plan-file] [execution-report] (optional - auto-detects)
model: opus
---

# System Review: Meta-Process Analysis

## Objective

Perform **meta-level analysis** of how well the implementation followed the plan,
and extract actionable improvements for the AI workflow system itself.

**Philosophy**:

- Good divergence reveals plan limitations → improve `/plan` command
- Bad divergence reveals unclear requirements → improve communication patterns
- Repeated issues reveal missing automation → create new commands

**This is NOT code review.** You're looking for bugs in the *process*, not the code.

---

## Phase 1: Input Resolution

### If arguments provided

- Plan file: first argument
- Execution report: second argument

### If no arguments (auto-detect)

1. Find recent execution reports:

    ```text
    Glob(".agents/execution-reports/*.md")
    ```

2. Sort by modification time, present options:

    ```text
    AskUserQuestion:
    "Which execution report should I analyse?"
    Options: [list of 3-4 most recent reports]
    ```

3. Extract plan file path from selected report's "Plan file" field

4. Confirm with user:

    ```text
    AskUserQuestion:
    "Analyse this plan and report pair?"
    - Plan: {extracted path}
    - Report: {selected path}
    Options: [Proceed, Select different files]
    ```

---

## Phase 2: Context Loading

Read all four key artifacts:

### 1. Plan Command

```text
Read(".claude/commands/workflow/plan.md")
```

Extract: What instructions guide plan creation?

### 2. Generated Plan

```text
Read("{plan-file}")
```

Extract: What was the agent SUPPOSED to do?

### 3. Implement Command

```text
Read(".claude/commands/workflow/implement.md")
```

Extract: What instructions guide implementation?

### 4. Execution Report

```text
Read("{execution-report}")
```

Extract: What did the agent ACTUALLY do and why?

---

## Phase 3: Divergence Classification

For each divergence documented in the execution report:

### Good Divergence ✅ (Justified)

| Indicator | Example |
|-----------|---------|
| Plan assumed non-existent pattern | "Plan referenced `utils.py` which doesn't exist" |
| Better pattern discovered | "Found existing helper that does this better" |
| Performance optimisation needed | "Original approach would cause N+1 queries" |
| Security issue discovered | "Planned approach had injection vulnerability" |

**Action**: Improve plan command to catch this earlier.

### Bad Divergence ❌ (Problematic)

| Indicator | Example |
|-----------|---------|
| Ignored explicit constraints | "Plan said use existing auth, created new one" |
| Created new architecture | "Built custom ORM instead of using existing" |
| Took shortcuts | "Skipped tests to save time" |
| Misunderstood requirements | "Built X when Y was requested" |

**Action**: Improve communication clarity or add validation.

---

## Phase 4: Root Cause Analysis

For each problematic divergence, trace the root cause:

| Root Cause | Symptoms | Fix Location |
|------------|----------|--------------|
| **Plan unclear** | Ambiguous instructions led to wrong choice | `/plan` command |
| **Context missing** | Necessary patterns not referenced | `/plan` context gathering |
| **Validation missing** | Issue not caught until late | `/implement` validation |
| **Manual step repeated** | Same manual work done 3+ times | New command needed |
| **Convention undocumented** | Agent didn't know project pattern | `CLAUDE.md` |

---

## Phase 5: Generate Improvements

### Categories of Improvements

#### 1. CLAUDE.md Updates

Patterns or anti-patterns to document globally:

```markdown
## Add to CLAUDE.md

### Pattern: {name}
{Description of pattern discovered during implementation}

### Anti-pattern: {name}
{Description of what NOT to do and why}
```

#### 2. Plan Command Updates

Instructions to add/clarify in `/plan`:

```markdown
## Update .claude/commands/workflow/plan.md

### Add to Phase X:
- {New instruction or check}

### Clarify:
- {Ambiguous instruction} → {Clearer version}
```

#### 3. Implement Command Updates

Validation or process steps to add:

```markdown
## Update .claude/commands/workflow/implement.md

### Add validation:
- {New check before/after implementation}

### Add reminder:
- {Common mistake to warn about}
```

#### 4. New Command Proposals

For manual processes repeated 3+ times:

```markdown
## Proposed New Command: /{command-name}

**Purpose**: {What it automates}
**Trigger**: {When to use it}
**Saves**: {What manual work it eliminates}
```

---

## Phase 6: Generate Report

Write analysis to: `.agents/system-reviews/{feature-name}-review.md`

Use this structure:

````markdown
# System Review: {Feature Name}

**Plan reviewed**: {path}
**Execution report**: {path}
**Date**: {current date}

---

## Overall Alignment Score: X/10

| Score | Meaning |
|-------|---------|
| 9-10 | Perfect adherence, all divergences justified |
| 7-8 | Minor justified divergences |
| 5-6 | Mix of justified and problematic divergences |
| 3-4 | Major problematic divergences |
| 1-2 | Significant process failures |

**Rationale**: {Why this score}

---

## Divergence Analysis

### Divergence 1: {Title}

```yaml
divergence: {What changed}
planned: {What plan specified}
actual: {What was implemented}
reason: {Agent's stated reason from report}
classification: good ✅ | bad ❌
justified: yes | no
root_cause: {Unclear plan | Missing context | Missing validation | etc}
```

**Improvement**: {Specific fix for this divergence}

{Repeat for each divergence...}

---

## Pattern Compliance

| Criterion | Status | Notes |
|-----------|--------|-------|
| Followed codebase architecture | ✓/✗ | {details} |
| Used documented patterns (CLAUDE.md) | ✓/✗ | {details} |
| Applied testing patterns correctly | ✓/✗ | {details} |
| Met validation requirements | ✓/✗ | {details} |

---

## Actionable Improvements

### Update CLAUDE.md

Priority: {High/Medium/Low}

```markdown
{Exact text to add to CLAUDE.md}
```

**Rationale**: {Why this helps}

---

### Update /plan Command

Priority: {High/Medium/Low}

```markdown
{Exact text to add/modify in plan.md}
```

**Rationale**: {Why this helps}

---

### Update /implement Command

Priority: {High/Medium/Low}

```markdown
{Exact text to add/modify in implement.md}
```

**Rationale**: {Why this helps}

---

### Proposed New Commands

{If applicable}

```markdown
---
description: {description}
---

# /{command-name}

{Command skeleton}
```

**Rationale**: {What manual process this automates}

---

## Key Learnings

### What Worked Well

- {Specific process strengths}

### What Needs Improvement

- {Specific process gaps}

### For Next Implementation

- {Concrete improvements to apply}

---

## Summary

**Process health**: {Overall assessment}

**Top 3 actions**:
1. {Most impactful improvement}
2. {Second priority}
3. {Third priority}

**Ready for**: User to review and apply suggested improvements
````

---

## Phase 7: Offer to Apply Changes

After generating the report, ask user:

```text
AskUserQuestion:
"Would you like me to apply any of the suggested improvements?"
Options:
- Apply all high-priority changes
- Apply changes to CLAUDE.md only
- Apply changes to commands only
- Review report first, apply nothing yet
```

If user chooses to apply:

- Use Edit tool to make the changes
- Show diff of what was changed
- Suggest running `/convert-prompts` if commands were modified

---

## Important Notes

- **Be specific**: Don't say "plan was unclear" - say "plan didn't specify which auth pattern to use"
- **Focus on patterns**: One-off issues aren't actionable. Look for repeated problems.
- **Action-oriented**: Every finding must have a concrete fix with exact text to add
- **Suggest, don't assume**: Always confirm before modifying CLAUDE.md or commands
- **Think systemically**: How does this improvement prevent future similar issues?

ultrathink
