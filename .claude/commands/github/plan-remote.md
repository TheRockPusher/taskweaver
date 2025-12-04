---
description: Create autonomous implementation plan and push to new GitHub branch
allowed-tools:
  - Read
  - Glob
  - Grep
  - Write
  - WebSearch
  - WebFetch
  - Task
  - TodoWrite
  - Bash(git status:*)
  - Bash(git branch:*)
  - Bash(git checkout:*)
  - Bash(git add:*)
  - Bash(git commit:*)
  - Bash(git push:*)
  - Bash(git ls-files:*)
  - Bash(git remote:*)
argument-hint: <feature-description>
model: opus
---

# Plan Remote: Autonomous GitHub Planning Workflow

## Feature: $ARGUMENTS

## Mission

Transform a feature request into a **comprehensive, autonomous implementation plan**
optimized for remote GitHub workflows with minimal user intervention.

**Core Principle**: Make intelligent defaults, document all assumptions, create
context-rich plans that enable fully autonomous implementation.

**Workflow**: Plan → Branch → Commit → Push → Ready for Remote Implementation

**Autonomy Philosophy**: Only ask user questions for truly ambiguous architectural
decisions. For everything else, choose the most reasonable default based on codebase
patterns and industry best practices, then document the decision clearly.

---

## Phase 0: Environment Setup

**Check git state and prepare for autonomous workflow:**

1. **Verify git repository**

   ```bash
   git status
   git remote -v
   ```

2. **Confirm on main/master branch**
   - If on feature branch, note it but continue
   - Document current branch in plan metadata

3. **Check for uncommitted changes**
   - If changes exist, document but continue (won't affect plan creation)
   - Plan branch will be created from current HEAD

---

## Phase 1: Project Rules Check

**MANDATORY FIRST STEP:**

1. Read `CLAUDE.md` or `AGENTS.md` if present
2. Extract project-specific conventions and forbidden patterns
3. Note required tools, testing frameworks, and validation commands
4. Identify any AI-specific instructions that override defaults

**If project rules missing**: Use industry standard conventions for detected
language/framework. Document this assumption in plan.

---

## Phase 2: Feature Understanding & Autonomous Decision Making

**Analyse feature deeply:**

- **Core problem** being solved
- **User value** and business impact
- **Feature type**: Auto-classify as New Capability / Enhancement / Refactor / Bug Fix
- **Complexity**: Auto-assess as Low / Medium / High based on scope
- **Affected systems** and components

**Autonomous Decision Framework:**

| Scenario | Default Decision | Document In Plan |
| -------- | ---------------- | ---------------- |
| Unclear naming | Use codebase patterns or language conventions | Yes - explain choice |
| Missing test framework | Infer from package.json/pyproject.toml | Yes - note inference |
| Ambiguous architecture | Choose simplest approach that works | Yes - rationale required |
| Multiple valid patterns | Use most common in codebase | Yes - reference examples |
| External library choice | Use existing if available, else popular choice | Yes - justify selection |

**Only use AskUserQuestion if:**

- Security implications (auth, permissions, data access)
- Breaking changes to public APIs
- Significant performance trade-offs (e.g., O(n) vs O(n²) with large n)
- Multiple valid architectures with no clear winner

---

## Phase 3: Codebase Intelligence Gathering

**Launch parallel analysis agents:**

```text
Agent 1: Project Structure
- Languages, frameworks, runtime versions
- Directory structure and architectural patterns
- Configuration files (pyproject.toml, package.json, etc.)
- Infer missing details from standard conventions

Agent 2: Pattern Recognition
- Similar implementations in codebase
- Naming conventions (CamelCase, snake_case)
- Error handling and logging patterns
- Extract real examples, not placeholders

Agent 3: Testing Patterns
- Test framework and structure
- Coverage requirements or reasonable defaults
- Similar test examples to mirror
- If no tests exist, use framework best practices

Agent 4: Integration Points
- Files needing updates
- New files and their locations
- Router/API registration patterns
- Infer patterns from existing structure
```

**For each agent, extract:**

- Specific file paths with line numbers
- Real code examples (not placeholders)
- Anti-patterns to avoid
- **Auto-fill gaps** with reasonable defaults when patterns unclear

---

## Phase 4: External Research

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

**If research inconclusive**: Document multiple approaches with pros/cons,
choose one as default recommendation.

---

## Phase 5: Strategic Thinking & Autonomous Design

**Think deeply about:**

- How does this fit into existing architecture?
- What are critical dependencies and order of operations?
- What could go wrong? (Edge cases, race conditions, errors)
- How will this be tested comprehensively?
- Performance implications?
- Security considerations?
- Maintainability?

**Design Decisions (Make Autonomously):**

- Choose between alternatives with clear rationale
- Design for extensibility with current requirements
- Plan for backward compatibility if touching existing APIs
- **Document every significant design choice** in NOTES section

**Decision Documentation Template:**

```markdown
**Decision**: [What was chosen]
**Alternatives Considered**: [A, B, C]
**Rationale**: [Why this choice based on codebase/requirements]
**Risk**: Low/Medium/High
```

---

## Phase 6: Plan Generation

Write plan to `.agents/plans/{kebab-case-feature-name}.md`

**Use base template**: `.claude/commands/shared/plan-template-base.md`

### Autonomous Workflow Customizations

**1. Add autonomous plan header** (before Overview):

```markdown
> **AUTONOMOUS PLAN**: This plan was generated with minimal user input.
> All design decisions are documented below. Review NOTES section for assumptions.
```

**2. Extend Metadata table** with autonomous tracking:

| Field            | Value                                          |
|------------------|------------------------------------------------|
| Autonomy Level   | Fully Autonomous / Semi-Autonomous             |
| Assumptions Made | {Number of documented assumptions}             |

**3. Update Boundaries section** to include remote workflow requirements:

**ALWAYS:**

- {Standard patterns from base template}
- Commit incrementally during implementation
- Push after validation passes

**ASK FIRST:**

- {Only truly ambiguous architectural decisions}

**NEVER:**

- {Standard prohibitions from base template}
- Skip validation commands

**4. Add phase validation hints** in Implementation Plan:

- Phase 1: `**Validation**: Run lint and type check after this phase`
- Phase 2: `**Validation**: Run all unit tests after this phase`
- Phase 3: `**Validation**: Run integration tests after this phase`
- Phase 4: `**Validation**: Run full validation suite`

**5. Add fallback validation commands** (if project commands not found):

```bash
# Level 1: npx eslint . || ruff check . || cargo fmt --check
# Level 2: npx tsc --noEmit || mypy . || cargo check
# Level 3: npm test || pytest || cargo test
# Level 4: Note if no integration tests defined
```

**6. Update ACCEPTANCE CRITERIA** with remote workflow requirements:

- [ ] Branch pushed to remote for review
- [ ] Unit test coverage meets requirements (or ≥80% if undefined)

**7. Extend EXECUTION TODOS** for remote workflow:

1. Verify on correct feature branch
2. {Standard implementation phases with per-phase validation/commit}
3. Run all validation commands (iterate until pass)
4. Update documentation if needed
5. Final commit with all changes
6. Push branch to remote

**8. Add comprehensive NOTES & AUTONOMOUS DECISIONS section**:

```markdown
## NOTES & AUTONOMOUS DECISIONS

### Assumptions Made

1. **Assumption**: {What was assumed}
   - **Basis**: {Why this assumption is reasonable}
   - **Risk**: Low/Medium/High
   - **Fallback**: {What to do if assumption invalid}

### Design Decisions

1. **Decision**: {What was chosen}
   - **Alternatives**: {Other options considered}
   - **Rationale**: {Why this choice}
   - **Impact**: {Affected components}

### Risks & Mitigations

1. **Risk**: {Potential issue}
   - **Likelihood**: Low/Medium/High
   - **Impact**: Low/Medium/High
   - **Mitigation**: {How to address}

### Trade-offs

- **Chose**: {Option A}
- **Over**: {Option B}
- **Because**: {Reason}
- **Accept**: {Downside of choice}
```

**9. Add REMOTE WORKFLOW METADATA section** at end:

```markdown
## REMOTE WORKFLOW METADATA

**Generated For**: Remote/Async GitHub Workflow
**User Input Required**: Minimal (only if truly ambiguous)
**Branch Name**: `feature/{kebab-case-name}` (will be created)
**Commit Message**: `docs: 📝 add implementation plan for {feature}`
**Next Command**: `/github:implement-remote .agents/plans/{plan-file}.md`
```

---

## Phase 7: Plan Quality Validation

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

### Autonomy Validation

- [ ] All assumptions explicitly documented
- [ ] Design decisions have clear rationale
- [ ] Fallback strategies noted for risky choices
- [ ] Only essential questions raised (if any)

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

- [ ] **Level 1 (Lint/Format)**: Specific command or reasonable default
- [ ] **Level 2 (Type Safety)**: Specific command or reasonable default
- [ ] **Level 3 (Unit Tests)**: Specific command or reasonable default
- [ ] **Level 4 (Integration Tests)**: Command or explicit "N/A"
- [ ] **Level 5 (Manual)**: Specific manual validation steps listed

---

## Phase 8: Branch Creation & Push

**Create and push feature branch:**

1. **Generate branch name**

   ```bash
   # Format: feature/{kebab-case-feature-name}
   # Example: feature/add-user-authentication
   ```

2. **Create branch**

   ```bash
   git checkout -b feature/{kebab-case-name}
   ```

3. **Add plan file**

   ```bash
   git add .agents/plans/{plan-file}.md
   ```

4. **Commit plan**

   ```bash
   git commit -m "docs: 📝 add implementation plan for {feature-name}

   - Generated autonomous plan with deep codebase analysis
   - Documented all assumptions and design decisions
   - Ready for remote implementation via /github:implement-remote"
   ```

5. **Push branch**

   ```bash
   git push -u origin feature/{kebab-case-name}
   ```

6. **Verify push**

   ```bash
   git status
   git branch -vv
   ```

---

## Phase 9: Output Report

After successful branch push, report:

### Plan Summary

**Feature**: {Feature name}
**Type**: {New Capability/Enhancement/Refactor/Bug Fix}
**Complexity**: {Low/Medium/High}

**Approach**: {2-3 sentence summary}

### File Locations

- **Plan File**: `.agents/plans/{filename}.md`
- **Branch**: `feature/{branch-name}`
- **Remote**: Pushed to origin

### Autonomy Report

**Assumptions Made**: {Number}
**Design Decisions**: {Number}
**User Questions Asked**: {Number (aim for 0-1)}

**Key Assumptions**:

1. {Brief assumption 1}
2. {Brief assumption 2}
3. {Brief assumption 3}

**Key Decisions**:

1. {Brief decision 1}
2. {Brief decision 2}

### Confidence & Risk

**Confidence Score**: {X/10}

- **Rationale**: {Why this score}

**Key Risks**:

1. {Risk 1} - Likelihood: {L/M/H}, Impact: {L/M/H}
2. {Risk 2} - Likelihood: {L/M/H}, Impact: {L/M/H}

### Next Steps

**Immediate Action**:

```bash
/github:implement-remote .agents/plans/{plan-file}.md
```

**Command will**:

- Verify on correct branch
- Implement plan with incremental commits
- Run validation after each phase
- Push changes automatically
- Suggest PR creation at completion

**Branch URL**: `https://github.com/{org}/{repo}/tree/feature/{branch-name}`

---

## Confidence Score Criteria

| Score | Meaning | Characteristics |
| ----- | ------- | --------------- |
| 9-10 | Fully Autonomous | All patterns clear, zero user questions, complete context |
| 7-8 | Mostly Autonomous | Minor gaps filled with reasonable defaults, well documented |
| 5-6 | Semi-Autonomous | Some user input needed during implementation likely |
| 3-4 | Limited Autonomy | Significant unknowns, user guidance recommended |
| 1-2 | Cannot Proceed | Major blockers, must get user input before implementing |

**Target**: 7-10 for remote workflows

---

## Guidelines

- **Make reasonable defaults**, don't wait for user input
- **Document every assumption** clearly in NOTES
- **Choose simplest approach** that meets requirements
- **Mirror existing patterns** whenever possible
- **Be specific**, avoid generic placeholders
- **Create actionable tasks**, not vague descriptions
- **Validate the plan** can succeed without you
- **Push the plan** so remote implementation can begin

ultrathink
