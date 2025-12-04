---
description: Create comprehensive implementation plan with deep codebase analysis
allowed-tools:
  - Read
  - Glob
  - Grep
  - Write
  - WebSearch
  - WebFetch
  - Task
  - TodoWrite
  - AskUserQuestion
argument-hint: <feature-description>
model: opus
---

# Plan: Create Implementation Plan

## Feature: $ARGUMENTS

## Mission

Transform a feature request into a **comprehensive implementation plan** through
systematic codebase analysis, external research, and strategic planning.

**Core Principle**: NO CODE in this phase. Create a context-rich plan that
enables one-pass implementation success.

**Key Philosophy**: Context is King. The plan must contain ALL information
needed—patterns, mandatory reading, documentation, validation commands—so
execution succeeds on first attempt.

---

## Phase 0: Project Rules Check

**MANDATORY FIRST STEP:**

1. Read `CLAUDE.md` or `AGENTS.md` if present
2. Extract project-specific conventions and forbidden patterns
3. Note required tools, testing frameworks, and validation commands
4. Identify any AI-specific instructions that override defaults

---

## Phase 1: Feature Understanding

Think hard about:

- **Core problem** being solved
- **User value** and business impact
- **Feature type**: New Capability / Enhancement / Refactor / Bug Fix
- **Complexity**: Low / Medium / High
- **Affected systems** and components

**If requirements are unclear**: Use AskUserQuestion tool before proceeding.

---

## Phase 2: Codebase Intelligence Gathering

**Launch parallel analysis agents:**

```text
Agent 1: Project Structure
- Languages, frameworks, runtime versions
- Directory structure and architectural patterns
- Configuration files (pyproject.toml, package.json, etc.)

Agent 2: Pattern Recognition
- Similar implementations in codebase
- Naming conventions (CamelCase, snake_case)
- Error handling and logging patterns

Agent 3: Testing Patterns
- Test framework and structure
- Coverage requirements
- Similar test examples

Agent 4: Integration Points
- Files needing updates
- New files and their locations
- Router/API registration patterns
```

**For each agent, extract:**

- Specific file paths with line numbers
- Real code examples (not placeholders)
- Anti-patterns to avoid

---

## Phase 3: External Research

**Documentation Lookup Priority:**

1. **llms.txt first** - Check `https://{domain}/llms.txt` or `/llms-full.txt`
2. **Context7 MCP** - Use `resolve-library-id` + `get-library-docs` if available
3. **MCP servers** - Check [MCP servers](https://github.com/modelcontextprotocol/servers)
4. **Official docs** - Direct documentation with section anchors
5. **Web search** - Last resort

**Gather:**

- Latest library versions and best practices
- Implementation examples and tutorials
- Common gotchas and known issues
- Breaking changes and migration guides

---

## Phase 4: Strategic Thinking

Think harder about:

- How does this fit into existing architecture?
- What are critical dependencies and order of operations?
- What could go wrong? (Edge cases, race conditions, errors)
- How will this be tested comprehensively?
- Performance implications?
- Security considerations?
- Maintainability?

**Design Decisions:**

- Choose between alternatives with clear rationale
- Design for extensibility
- Plan for backward compatibility if needed

---

## Phase 5: Plan Generation

Write plan to `.agents/plans/{kebab-case-feature-name}.md`

**Use base template**: `.claude/commands/shared/plan-template-base.md`

### Interactive Workflow Notes

For interactive workflows, the base template is used as-is with no customizations.
The user will be available to answer questions and make decisions during implementation.

**Key differences from autonomous plans**:

- No autonomous decision framework (use AskUserQuestion liberally)
- No assumptions documentation (ask instead)
- No incremental commit requirements (user controls git)
- Standard NOTES section for general context

---

## Phase 6: Plan Quality Validation

**Self-Review Checklist:**

### Context Completeness

- [ ] All necessary patterns identified with file:line references
- [ ] External library usage documented with links
- [ ] Integration points clearly mapped
- [ ] Gotchas and anti-patterns captured
- [ ] Every task has executable validation command

### Implementation Ready

- [ ] Another developer could execute without additional context
- [ ] Tasks ordered by dependency (top-to-bottom execution)
- [ ] Each task is atomic and independently testable
- [ ] Pattern references include specific file:line numbers

### Pattern Consistency

- [ ] Tasks follow existing codebase conventions
- [ ] New patterns justified with rationale
- [ ] No reinvention of existing utils/patterns
- [ ] Testing approach matches project standards

### Information Density

- [ ] No generic references (all specific and actionable)
- [ ] URLs include section anchors
- [ ] Task descriptions use codebase keywords
- [ ] Validation commands are executable (non-interactive)

### Validation Completeness (CRITICAL)

**MANDATORY**: The plan MUST include executable validation commands for all 5
levels:

- [ ] **Level 1 (Lint/Format)**: Specific command exists
  (e.g., `ruff check .`, `npm run lint`, `make lint`)
- [ ] **Level 2 (Type Safety)**: Specific command exists
  (e.g., `mypy .`, `npx tsc --noEmit`, `cargo check`)
- [ ] **Level 3 (Unit Tests)**: Specific command exists
  (e.g., `pytest`, `npm test`, `cargo test`)
- [ ] **Level 4 (Integration Tests)**: Command or note if not applicable
- [ ] **Level 5 (Manual)**: Specific manual validation steps listed

If any validation command is missing or generic (e.g., "run tests"),
the plan is INCOMPLETE.

**How to find validation commands:**

1. Read CLAUDE.md for project-specific commands
2. Check for Makefile targets (`make check`, `make test`)
3. Check package.json scripts (`npm run lint`, `npm run test`)
4. Check pyproject.toml for tool configurations
5. Look for CI/CD files (.github/workflows/) for validation patterns

**If validation commands don't exist in the project:**

- Document that validation infrastructure needs to be added first
- Include task to add linting/testing setup
- Ask user what validation approach they want

---

## Confidence Score Criteria

| Score | Meaning | Action |
| ----- | ------- | ------ |
| 9-10 | All patterns identified, clear path, no ambiguity | Proceed |
| 7-8 | Minor unknowns, solid foundation | Proceed with notes |
| 5-6 | Some gaps, may need clarification during execution | Review with user |
| 3-4 | Significant unknowns | Ask user for input |
| 1-2 | Major blockers | Cannot proceed |

**Score below 7?** Ask user for clarification before finalising.

---

## Plan Size Guidelines

- **Target**: 200-400 lines for typical features
- **Maximum**: 800 lines (larger plans should split)
- **Why**: Large plans hit context limits in some tools

**If plan exceeds 500 lines**, consider splitting:

- `.agents/plans/{feature}-part1-foundation.md`
- `.agents/plans/{feature}-part2-implementation.md`

---

## Output

After creating the plan, report:

1. **Summary**: Feature and approach (2-3 sentences)
2. **File path**: Full path to created plan
3. **Complexity**: Low / Medium / High with rationale
4. **Key risks**: Implementation risks or considerations
5. **Confidence score**: X/10 with brief justification

ultrathink
