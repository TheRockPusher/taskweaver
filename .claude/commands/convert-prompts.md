---
description: Convert Claude commands to GitHub/Codex prompt format
allowed-tools:
  - Read
  - Write
  - Glob
model: haiku
---

# Convert Claude Commands to GitHub Prompts

Convert `.claude/commands/*.md` files to `.github/prompts/*.prompt.md` format.

## Process

1. **Find all Claude commands** - Glob `.claude/commands/*.md`, exclude this file
2. **Parse each file** - Read content and YAML frontmatter
3. **Transform to GitHub format** (see below)
4. **Write to `.github/prompts/{filename}.prompt.md`**
5. **Report what was converted**

## Format Transformation

**From (Claude):**

```yaml
---
description: ...
allowed-tools: [...]
---
```

**To (GitHub/Codex):**

```yaml
---
description: ...
agent: agent
---
```

**Changes:**

- Remove `allowed-tools` (not compatible across platforms)
- Remove `model` (Claude-specific)
- Remove `argument-hint` (use `${input:name}` syntax in body instead)
- Add `agent: agent` for agentic mode
- Keep the prompt body unchanged

## Notes

- Tool names differ between Claude and GitHub, so we remove them
- The prompt body is plain Markdown, works everywhere
- `agent: agent` enables agentic mode in GitHub Copilot
