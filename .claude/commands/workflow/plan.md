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
- **Namespace conflicts?** (Module filenames mustn't match exported instance names)

**Design Decisions:**

- Choose between alternatives with clear rationale
- Design for extensibility
- Plan for backward compatibility if needed

---

## Phase 5: Plan Generation

Write the plan to `.agents/plans/{kebab-case-feature-name}.md` using this template:

````markdown
# Feature: {Feature Name}

> **IMPORTANT**: Validate documentation and codebase patterns before implementing.
> Pay attention to naming of existing utils, types, and models.
> Import from correct files.

## Overview

**Description**: {Detailed description, purpose, user value}
**Problem**: {Specific problem or opportunity addressed}
**Solution**: {Proposed approach and how it solves the problem}

## Metadata

| Field | Value |
|-------|-------|
| Type | New Capability / Enhancement / Refactor / Bug Fix |
| Complexity | Low / Medium / High |
| Systems Affected | {List components/services} |
| Dependencies | {External libraries or services} |

---

## CONTEXT REFERENCES

### Mandatory Reading (READ BEFORE IMPLEMENTING)

- `path/to/file.py:15-45` - Why: Contains pattern for X to mirror
- `path/to/model.py:100-120` - Why: Database model structure
- `path/to/test.py` - Why: Test pattern example

### New Files to Create

- `path/to/new_service.py` - Service for X functionality
- `path/to/new_model.py` - Data model for Y resource
- `tests/path/to/test_new_service.py` - Unit tests

### Documentation References

- [Library Docs](https://example.com/docs#section) - Why: X functionality
- [Framework Guide](https://example.com/guide#integration) - Why: Integration patterns

### Patterns to Follow

**Naming:**
```{language}
# Example from codebase
```

**Error Handling:**
```{language}
# Example from codebase
```

**Logging:**
```{language}
# Example from codebase
```

### Boundaries

**ALWAYS:**
- {Mandatory patterns from CLAUDE.md}
- {Required validation before commit}

**ASK FIRST:**
- {Changes requiring user confirmation}
- {Architectural decisions}

**NEVER:**
- {Forbidden patterns}
- {Files not to modify}
- {Security anti-patterns}

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation
{Foundational work before main implementation}

**Tasks:**
- Set up base structures (schemas, types, interfaces)
- Configure dependencies
- Create foundational utilities

### Phase 2: Core Implementation
{Main implementation work}

**Tasks:**
- Implement core business logic
- Create service layer components
- Add API endpoints/interfaces
- Implement data models

### Phase 3: Integration
{How feature integrates with existing functionality}

**Tasks:**
- Connect to existing routers/handlers
- Register new components
- Update configuration
- Add middleware if needed

### Phase 4: Testing & Validation
{Testing approach}

**Tasks:**
- Unit tests for each component
- Integration tests for workflows
- Edge case tests
- Acceptance criteria validation

---

## STEP-BY-STEP TASKS

> Execute every task in order, top to bottom. Each task is atomic and testable.

### Task Keywords
- **CREATE**: New files or components
- **UPDATE**: Modify existing files
- **ADD**: Insert functionality into existing code
- **REMOVE**: Delete deprecated code
- **REFACTOR**: Restructure without changing behaviour
- **MIRROR**: Copy pattern from elsewhere

### {ACTION} {target_file}

- **IMPLEMENT**: {Specific implementation detail}
- **PATTERN**: {Reference to existing pattern - file:line}
- **IMPORTS**: {Required imports}
- **GOTCHA**: {Known issues or constraints}
- **VALIDATE**: `{executable command}`

{Continue with all tasks in dependency order...}

---

## TESTING STRATEGY

### Unit Tests
{Scope based on project standards}

### Integration Tests
{Scope based on project standards}

### Edge Cases
- {Specific edge case 1}
- {Specific edge case 2}

---

## VALIDATION COMMANDS

> Execute every command to ensure zero regressions.

### Level 1: Syntax & Style
```bash
{project-specific lint/format commands}
```

### Level 2: Type Check
```bash
{project-specific type check commands}
```

### Level 3: Unit Tests
```bash
{project-specific test commands}
```

### Level 4: Integration Tests
```bash
{project-specific integration test commands}
```

### Level 5: Manual Validation
{Feature-specific manual testing steps}

---

## ACCEPTANCE CRITERIA

- [ ] Feature implements all specified functionality
- [ ] All validation commands pass with zero errors
- [ ] Unit test coverage meets requirements
- [ ] Integration tests verify end-to-end workflows
- [ ] Code follows project conventions
- [ ] No regressions in existing functionality
- [ ] Documentation updated (README, CLAUDE.md) if user-facing changes

---

## EXECUTION TODOS

> Pre-built todo structure for implementation agent:

1. Read all mandatory context files
2. Phase 1: Foundation tasks
3. Phase 2: Core implementation tasks
4. Phase 3: Integration tasks
5. Phase 4: Testing tasks
6. Run all validation commands
7. Verify acceptance criteria

---

## NOTES

{Additional context, design decisions, trade-offs, risks}
````

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
