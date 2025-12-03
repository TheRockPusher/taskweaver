---
description: Create a global rules file
allowed-tools:
  - Read
  - Glob
  - Grep
  - Task
  - Write
  - WebSearch
  - WebFetch
  - Bash(git ls-files:*)
  - Bash(git log:*)
  - Bash(git status:*)
  - Bash(tree:*)
  - Bash(wc -l:*)
  - Bash(ln -s:*)
  - Bash(npx markdownlint-cli:*)
  - AskUserQuestion
argument-hint: [project-path] (optional)
model: opus
---

# Global File Maker

## Goal

Create a concise, actionable `CLAUDE.md` file that guides AI assistants and developers.

## Architecture Context

When creating CLAUDE.md, recommend this folder structure:

```text
project/
├── CLAUDE.md              # AI rules (source of truth)
├── AGENTS.md              # Symlink → CLAUDE.md
├── .agents/
│   ├── PRD.md             # Product requirements
│   ├── plans/             # Feature implementation plans
│   └── reference/         # Architecture docs
└── .claude/
    └── commands/          # Reusable slash commands
```

**PIV Workflow:** Plan → Implement → Validate loop for each task.

**Documentation lookup:** llms.txt → Context7 MCP → Official docs → Web search.

**IMPORTANT:** Analyse whether this is a new or existing project FIRST:

- **Existing project** → Analyse codebase, extract conventions
- **New project** → Ask clarifying questions, then research 2025 best practices online

---

## CLAUDE.md Structure (100-500 lines MAX)

### Required Sections

| Section | What to Include |
|---------|-----------------|
| **1. Core Principles** | Non-negotiable rules (type safety, naming, logging). Short bullets. |
| **2. Tech Stack** | Languages, frameworks, tools with versions. Concise list. |
| **3. Architecture** | Folder structure, layer patterns, key files. Include tree diagram. |
| **4. Code Style** | Naming conventions + code examples. Show, don't tell. |
| **5. Logging** | Format, levels, what to log. Include code example. |
| **6. Testing** | Framework, patterns, how to run. Include test example. |
| **7. Common Patterns** | 2-3 real code patterns from codebase (repository, service, etc.) |
| **8. Dev Commands** | Install, test, lint, format, run commands. |
| **9. AI Assistant Instructions** | 10 bullet points for AI behaviour in this codebase. |

**Optional:** API Contracts (full-stack), Database conventions, Deployment notes

---

## AI-Aware Documentation Section

**CRITICAL:** Include guidance for AI assistants to find accurate, up-to-date documentation:

```markdown
## Documentation & Library Lookup

When researching libraries or APIs:

1. **Check for llms.txt first** - Many sites provide LLM-optimised docs:
   - `/{library}/llms.txt` (navigation/summary)
   - `/{library}/llms-full.txt` (complete docs in one file)
   - Standard defined at: https://llmstxt.org/

2. **Use Context7 MCP** - For up-to-date, version-specific library docs:
   - Call `resolve-library-id` with library name
   - Then `get-library-docs` with the resolved ID

3. **Check for MCP servers** - Before building integrations:
   - Database: Postgres, SQLite MCP servers
   - APIs: GitHub, Slack, Stripe, etc.
   - See: https://github.com/modelcontextprotocol/servers

4. **Fallback order:**
   llms.txt → Context7 MCP → Official docs → Web search
```

---

## Writing Style Guidelines

**Language:** Use British English spelling (colour, organisation, behaviour, analyse, centre)

**DO:**

- Use short, declarative bullets
- Include real code examples from the codebase
- Add emphasis: "IMPORTANT:", "NEVER:", "ALWAYS:"
- Keep sections focused and scannable
- Use tables for structured information

**DON'T:**

- Write long narrative paragraphs
- Include obvious/generic statements
- Add nice-to-have commentary
- Exceed 500 lines total

---

## Process

### Existing Projects

1. **Analyze codebase:**
   - `git ls-files` → understand structure
   - Read config files (pyproject.toml, package.json, etc.)
   - Review 3-5 representative files
   - Identify established patterns

2. **Extract conventions** using the structure above

3. **Use actual examples** from the codebase, not placeholders

4. **For large codebases**, launch parallel Task agents:
   - Agent 1: Analyse src/ structure and patterns
   - Agent 2: Analyse tests/ structure and conventions
   - Agent 3: Read config files and extract tech stack

### New Projects

1. **Ask clarifying questions:**
   - Project type? (web app, API, CLI, mobile)
   - Primary purpose/domain?
   - Technology preferences?
   - Scale/complexity?

2. **Research 2025 best practices** for the chosen stack

3. **Create rules** based on research + user preferences

---

## Modular Organisation (Optional)

For complex projects, use imports to keep CLAUDE.md focused:

```markdown
<!-- In CLAUDE.md -->
@.agents/reference/security-rules.md
@.agents/reference/testing-standards.md
@.agents/reference/project-conventions.md
```

---

## AI Assistant Instructions Template

Include ~10 bullets covering these areas:

```markdown
## AI Assistant Instructions

1. **Read CLAUDE.md first** before making changes
2. **Check llms.txt** for library docs (`/llms.txt`, `/llms-full.txt`)
3. **Use Context7 MCP** for up-to-date library documentation
4. **NEVER assume** - ask when requirements are unclear
5. **Run quality checks** before completing (`make check && make test`)
6. **Use entity-specific PKs** - `task_id` not `id`
7. **Write tests** for new functionality (80%+ coverage)
8. **Document decisions** with docstrings explaining "why"
9. **Use [package manager]** - never edit dependency files directly
10. **Follow existing patterns** - check similar files first
```

---

## Output Checklist

Before finalising CLAUDE.md:

- [ ] Under 500 lines (ideally 200-300)
- [ ] All code examples are real, not placeholders
- [ ] Uses short bullets, not paragraphs
- [ ] Includes AI documentation lookup guidance (llms.txt, Context7, MCP)
- [ ] Has emphasis on critical rules (IMPORTANT, NEVER, ALWAYS)
- [ ] Covers the 9 required sections
- [ ] Actionable - can be followed immediately
- [ ] Passes markdown linting with no errors

---

## Post-Creation

After creating CLAUDE.md:

1. **Lint the output:** `npx markdownlint-cli CLAUDE.md`
2. **Fix any linting errors** before proceeding
3. **Verify line count:** `wc -l CLAUDE.md` (must be under 500)
4. **Create AGENTS.md symlink:** `ln -s CLAUDE.md AGENTS.md`
5. **Run `/convert-prompts`** if `.claude/commands/` exists

Start by analysing the project structure now. For new projects, ask clarifying questions first.

ultrathink
