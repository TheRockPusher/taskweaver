---
description: Create a Product Requirements Document from conversation
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - WebSearch
  - WebFetch
  - Bash(npx markdownlint-cli:*)
  - Bash(wc -l:*)
  - AskUserQuestion
argument-hint: [output-filename]
model: opus
---

# Create PRD

## Purpose

Generate an AI-optimised Product Requirements Document from the current conversation. Output to `$ARGUMENTS` (default: `.agents/PRD.md`).

**Constraints:** Max 500 lines. Self-contained sections. British English.

## PRD Structure (8 Sections)

### Required Sections

| # | Section | Contents |
|---|---------|----------|
| 1 | **Executive Summary** | Product overview, value proposition, mission, core principles (3-5) |
| 2 | **Target Users** | User personas, technical level, pain points |
| 3 | **Scope & Boundaries** | In-scope (✅), out-of-scope (❌), plus three-tier boundaries |
| 4 | **Functional Requirements** | Categorised requirements with acceptance criteria |
| 5 | **Architecture & Stack** | High-level design, tech stack with versions, key patterns |
| 6 | **Implementation Phases** | 3-4 phases with deliverables and validation gates |
| 7 | **Success Criteria** | Measurable goals, quality indicators |
| 8 | **Risks & Mitigations** | 3-5 key risks with mitigation strategies |

### Optional Sections

| Section | When to Include |
|---------|-----------------|
| **Glossary** | Project has domain-specific terminology |
| **API Specification** | Project exposes or consumes APIs |
| **Security & Configuration** | Complex auth or deployment requirements |

## Three-Tier Boundary System

Include in **Scope & Boundaries** section:

```markdown
### Boundaries

**Always do:**
- Run tests before marking tasks complete
- Follow existing code patterns

**Ask first:**
- API schema changes
- New dependencies

**Never do:**
- Commit secrets or credentials
- Skip validation gates
```

## Validation Gates

Each implementation phase must include validation gates:

```markdown
### Phase 1: Foundation

**Deliverables:**
- [ ] Project structure created
- [ ] Core dependencies installed

**Validation:**
- [ ] `npm install` succeeds
- [ ] `npm test` passes
- [ ] Linting clean
```

## Process

1. **Extract** - Review conversation, identify requirements and constraints
2. **Research** - Check llms.txt for relevant library documentation
3. **Structure** - Organise into self-contained sections
4. **Write** - Generate PRD with clear, actionable language
5. **Validate** - Verify all sections present and consistent
6. **Lint** - Run markdown linter on output file, fix any issues

## AI-Optimised Writing Rules

| Rule | Rationale |
|------|-----------|
| **Self-contained sections** | AI processes chunks in isolation |
| **One term per concept** | Consistent terminology prevents confusion |
| **Explicit over implicit** | AI cannot infer unstated requirements |
| **Short, imperative rules** | Direct commands work better than suggestions |
| **Real code examples** | Concrete snippets over abstract descriptions |
| **Emphasis markers** | Use `IMPORTANT`, `NEVER`, `ALWAYS` for critical rules |

## Code Examples

Encourage concrete code snippets where helpful. Example directory structure:

```text
src/
├── api/           # API routes
├── services/      # Business logic
└── utils/         # Shared utilities
```

Example code pattern (Python):

```python
# Service layer pattern
class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def get_user(self, user_id: str) -> User:
        return self.repository.find_by_id(user_id)
```

## Quality Checklist

Before finalising the PRD:

- [ ] All 8 required sections present
- [ ] Each section self-contained (readable in isolation)
- [ ] Terminology consistent throughout
- [ ] Boundaries include always/ask/never tiers
- [ ] Each phase has validation gates
- [ ] Success criteria are measurable
- [ ] Under 500 lines total
- [ ] British English spelling

## Output

After creating the PRD:

1. Confirm file path written
2. Run `npx markdownlint-cli <file>` or equivalent to verify formatting
3. Fix any linting errors found
4. Summarise key contents (3-5 bullets)
5. Note assumptions made
6. Suggest next steps

## Notes

- Ask clarifying questions if critical information missing
- NEVER include timeline estimates (let user decide scheduling)
- Reference existing `.agents/PRD.md` patterns if available
- Adapt section depth based on project complexity

ultrathink
