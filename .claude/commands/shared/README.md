# Shared Command Components

**Purpose**: Reusable components to reduce duplication and improve maintainability across workflow commands.

**Philosophy**: Extract high-duplication, high-maintenance-value patterns while maintaining command independence and readability.

---

## Architecture Decision

### Why Shared Components?

**Research-backed approach** (Anthropic, 2025):
> "The most successful implementations use simple, composable patterns."
> — [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)

**Problem**: 85% template structure duplication between `workflow/plan.md` and `github/plan-remote.md` creates maintenance burden.

**Solution**: Extract shared base template, reference from both commands, allow workflow-specific customization.

**Trade-off Analysis**:

| Aspect              | Before Extraction     | After Extraction      |
|---------------------|------------------------|------------------------|
| **Duplication** | 85% template overlap | <5% (references only) |
| **Maintainability** | Update 2+ files | Update 1 template |
| **Readability** | Self-contained | Requires navigation |
| **Token usage** | ~19,890 total | ~19,240 total (-3%) |
| **Task following** | High (comprehensive) | High (maintained) |

**Verdict**: Benefits outweigh costs for high-duplication components.

---

## Current Components

### `plan-template-base.md` (210 lines)

**Purpose**: Shared plan structure for implementation plans

**Used by**:

- `.claude/commands/workflow/plan.md`
- `.claude/commands/github/plan-remote.md`

**Duplication reduced**: ~280 lines across 2 commands → 210 shared + ~20 references

**Customization**: Autonomous workflows add metadata rows and NOTES subsections

---

## When to Extract Components

### ✅ Good Candidates for Extraction

1. **High duplication** (>80% identical across commands)
2. **High maintenance burden** (changes frequently)
3. **Standalone value** (makes sense in isolation)
4. **Clear boundaries** (well-defined start/end)

**Examples**:

- ✅ Plan template structure (85% duplication, changes with process evolution)
- ✅ Task keywords definition (100% identical, conceptual foundation)
- ✅ Validation levels (90% identical, standardized framework)

### ❌ Poor Candidates for Extraction

1. **Low duplication** (<50% identical)
2. **Context-dependent logic** (behavior differs by workflow)
3. **Short sections** (<20 lines, extraction overhead not worth it)
4. **Rapidly diverging** (likely to differ in future)

**Examples**:

- ❌ Phase descriptions (45-70% similar, sync vs async semantics differ)
- ❌ Validation loops (60% conceptual, implementation details vary)
- ❌ Error handling (25% duplication, autonomous workflows fundamentally different)

---

## Usage Patterns

### Pattern 1: Template Reference (Recommended)

**In command file**:

```markdown
## Phase 5: Plan Generation

Write plan to `.agents/plans/{kebab-case-feature-name}.md`

**Use base template**: `.claude/commands/shared/plan-template-base.md`

**Customizations for this workflow**:
- Add metadata row: Autonomy Level
- Expand NOTES section with Assumptions and Design Decisions
```

**Benefits**:

- Clear separation of base vs. customization
- Command file remains readable
- Update template once, affects all users

### Pattern 2: Direct Inclusion (Not Supported Yet)

**Future possibility** (requires CLI support):

```markdown
<!-- Include: .claude/commands/shared/plan-template-base.md -->
```

**Currently**: Manual reference only

---

## Maintenance Workflow

### Updating Shared Components

**When**: Template structure changes, new validation levels, task keyword updates

**Process**:

1. **Edit shared component** (e.g., `plan-template-base.md`)
2. **Test with all consumers**:

   ```bash
   # Test workflow plan command
   /workflow:plan "sample feature"

   # Test autonomous plan command
   /github:plan-remote "sample feature"
   ```

3. **Verify customizations preserved** (check metadata additions, NOTES sections)
4. **Update documentation** if reference patterns change
5. **Run /convert-prompts** if changes affect GitHub Copilot compatibility

### Adding New Components

**Checklist**:

- [ ] Duplication >80% across 2+ commands?
- [ ] Component >20 lines?
- [ ] Changes would benefit multiple commands?
- [ ] Clear boundaries and standalone value?
- [ ] Customization points identified?

**If all yes**: Extract to `shared/`

### Removing Components

**When to consolidate back**:

- Only 1 consumer remains
- Components have diverged significantly
- Maintenance overhead exceeds duplication cost

---

## File Structure

```text
.claude/commands/shared/
├── README.md                    # This file
├── plan-template-base.md        # Shared plan structure (210 lines)
└── [future components]
```

**Future additions** (if duplication warrants):

- `validation-checklist.md` - Quality gate definitions
- `codebase-analysis.md` - Parallel analysis framework
- `autonomous-protocols.md` - Decision-making patterns

---

## Research Backing

### Anthropic Guidance on Modularity

> "These building blocks aren't prescriptive. They're common patterns that developers can shape and combine to fit different use cases."
> — [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)

### Token Efficiency vs. Task Following

**Research finding** (2025):
> "Claude 4.5 pays close attention to details and examples... specific instructions improve first-attempt success."

**Implication**: Detailed prompts help task following, but eliminate unnecessary duplication.

**Our approach**: Extract duplicates, maintain detail where it matters.

### Long Context Best Practices

> "Use XML tags or clear headers to structure complex inputs... this helps Claude maintain attention across long prompts."
> — [Long Context Tips](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/long-context-tips)

**Implementation**: Shared components use clear Markdown headers, maintaining structure when referenced.

---

## Version History

- **v1.0** (2025-12-04): Initial extraction of plan template base
- **v1.1** (future): Additional components as duplication identified

---

## Related Documentation

- `.agents/reference/command-optimization-proposal.md` - Full optimization analysis
- `.agents/reference/command-composition-analysis.md` - Technical feasibility study
- `.agents/reference/command-relationships.md` - Maintenance guide
- `CLAUDE.md` - Project-wide AI instructions
