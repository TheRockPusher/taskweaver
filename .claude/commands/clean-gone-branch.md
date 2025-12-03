---
description: Clean up git branches marked as [gone] from remote
allowed-tools:
  - Bash(git branch:*)
  - Bash(git worktree:*)
  - AskUserQuestion
model: haiku
---

# Clean: Remove Gone Branches

Clean up stale local branches that have been deleted from the remote repository.

## Process

### 1. List branches to identify [gone] status

```bash
git branch -v
```

Note: Branches with `+` prefix have associated worktrees.

### 2. Confirm with user

If [gone] branches found, use AskUserQuestion to confirm deletion.
Show list of branches that will be deleted.

**If no [gone] branches**: Report "No cleanup needed" and exit.

### 3. Check worktrees for [gone] branches

```bash
git worktree list
```

### 4. Remove worktrees and delete [gone] branches

```bash
git branch -v | grep '\[gone\]' | sed 's/^[+* ]//' | awk '{print $1}' | \
while read branch; do
  echo "Processing branch: $branch"
  worktree=$(git worktree list | grep "\\[$branch\\]" | awk '{print $1}')
  if [ -n "$worktree" ] && \
     [ "$worktree" != "$(git rev-parse --show-toplevel)" ]; then
    echo "  Removing worktree: $worktree"
    git worktree remove --force "$worktree"
  fi
  echo "  Deleting branch: $branch"
  git branch -D "$branch"
done
```

## Output

Report:

- Branches identified as [gone]
- Worktrees removed (if any)
- Branches deleted
- "No cleanup needed" if none found
