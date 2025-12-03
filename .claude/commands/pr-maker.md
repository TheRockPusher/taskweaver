---
description: Push current branch and create a GitHub PR
allowed-tools:
  - Bash(git status:*)
  - Bash(git log:*)
  - Bash(git diff:*)
  - Bash(git branch:*)
  - Bash(git push:*)
  - Bash(gh auth:*)
  - Bash(gh pr:*)
  - Bash(gh issue:*)
  - Read
  - Glob
  - AskUserQuestion
argument-hint: [base-branch]
model: haiku
---

# PR: Create Pull Request

Create a professional, concise pull request following best practices.

## Process

### 1. Read project conventions

Check for CLAUDE.md or AGENTS.md and note any PR-specific guidelines.

### 2. Validate prerequisites

- Check git status for commits to push
- Verify gh CLI authenticated (`gh auth status`)
- Confirm current branch is not main/master

### 3. Gather context

- Get current branch name
- Read commit messages: `git log origin/main..HEAD --oneline`
- Check diff summary for scope
- Search for related issue numbers

### 4. Push branch

```bash
git push -u origin <branch-name>
```

### 5. Create PR

Use `gh pr create` with structured format:

**Title**: `[Type] Brief description` (50 chars max)

Types: `[Feature]`, `[Fix]`, `[Refactor]`, `[Docs]`, `[Test]`, `[Chore]`

**Body template** (under 100 words total):

```markdown
## Summary

[1-2 sentences: what changed and why]

## Changes

- [Key change 1]
- [Key change 2]

Closes #[issue] (if applicable)
```

### 6. Best practices

- **Under 100 words** - be ruthlessly concise
- One sentence for "what", one for "why"
- 2-4 bullet points for changes
- No fluff or filler words

## Output

- Display PR URL
- Confirm creation success

## Error Handling

- No commits: inform and exit
- gh not authenticated: prompt `gh auth login`
- On main/master: warn and confirm
- Push fails: show error and troubleshooting
