# Value Scoring System Upgrade

## Overview

Upgraded from single-dimensional 0-10 scale to **multi-dimensional 0-100 scale** with user-specific personalization.

## Changes Made

### 1. Schema Changes
- **Scale**: 0-10 → 0-100 (better granularity)
- **Dimensions**: Single "impact" → Three dimensions (Financial, Knowledge, Strategic)
- **Personalization**: Generic → User-specific with mandatory context gathering

### 2. Files Modified

#### `/src/taskweaver/agents/prompts/orchestrator_prompt.md`
- **Lines 79, 94**: Updated scale references (0-10 → 0-100)
- **Lines 114-199**: Complete value scoring framework replacement
  - Three-dimensional scoring system
  - Financial value anchors ($-based)
  - Knowledge value anchors (skill development)
  - Strategic value anchors (goal alignment)
  - Clarification protocol
  - Concrete examples with calculations
- **Lines 220-223**: Updated priority calculation examples
- **Line 255**: Updated example task with 3D value breakdown

### 3. Core Framework

```
llm_value = (Financial × 0.35) + (Knowledge × 0.30) + (Strategic × 0.35)
```

**Financial (35% weight)**: Direct/indirect $ impact over 12 months
- 90-100: $10,000+ impact
- 70-89: $2,000-$10,000 impact
- 50-69: $500-$2,000 impact
- 30-49: $100-$500 impact
- 0-29: <$100 impact

**Knowledge (30% weight)**: Skill development and learning for user's career
- 90-100: Transformative capability
- 70-89: Significant skill development
- 50-69: Solid learning value
- 30-49: Modest learning
- 0-29: Minimal/no learning

**Strategic (35% weight)**: Goal alignment and long-term positioning
- 90-100: Mission-critical for goals
- 70-89: Strong goal alignment
- 50-69: Moderate relevance
- 30-49: Weak alignment
- 0-29: No strategic value

## Testing Scenarios

### Scenario 1: High-Value Strategic Task

**Task**: "Build authentication system for SaaS MVP"
**User Context**: Launching startup, auth blocks revenue

**Expected Scoring:**
- Financial: 95 (blocks $50k+ revenue)
- Knowledge: 65 (deepening existing skill)
- Strategic: 95 (critical path for primary goal)
- **Final: 86.8**

**Expected Behavior**: AI recognizes this as exceptional priority

---

### Scenario 2: Pure Learning Task

**Task**: "Complete Rust fundamentals course"
**User Context**: Exploring new language, no immediate application

**Expected Scoring:**
- Financial: 15 (no current financial impact)
- Knowledge: 85 (major new high-demand skill)
- Strategic: 55 (interesting but not required for goals)
- **Final: 50.3**

**Expected Behavior**: Moderate priority - valuable learning but not urgent

---

### Scenario 3: Low-Value Busywork

**Task**: "Reorganize project folder structure"
**User Context**: Existing projects, no pressing issues

**Expected Scoring:**
- Financial: 35 (saves 1-2 hours over 6 months)
- Knowledge: 10 (no new skills)
- Strategic: 15 (not goal-related)
- **Final: 20.5**

**Expected Behavior**: AI should surface this as low-value, potentially suggest skipping

---

### Scenario 4: User-Specific Differentiation

**Task**: "Learn Python basics"

**User A (beginner seeking programming job):**
- Financial: 70 (enables $5k+ salary increase)
- Knowledge: 90 (foundational transformative skill)
- Strategic: 85 (required for career goal)
- **Final: 81.8**

**User B (senior dev exploring):**
- Financial: 10 (already proficient, no impact)
- Knowledge: 15 (no new learning)
- Strategic: 20 (not aligned with goals)
- **Final: 15.0**

**Expected Behavior**: Same task, wildly different scores based on user context

---

## Clarification Protocol Testing

### Test Case 1: Insufficient Context

**User says**: "I want to build a blog"

**Expected AI Response**:
```
To score this accurately for YOUR situation, I need some context:

1. **Financial**: Is this blog intended to generate income (ads, sponsorships, lead gen)?
   What's your income goal for the next year?

2. **Knowledge**: Do you already know web development, or is this a learning project?
   What technical skills do you currently have?

3. **Strategic**: What are your top 2-3 goals for the next year?
   How does this blog connect to those goals?

This helps me give you a personalized value score rather than a generic one.
```

**After receiving context, AI should provide appropriate scores.**

---

### Test Case 2: Ambiguous Financial Impact

**User says**: "I want to learn AWS"

**Expected AI Response**:
```
To score the financial value accurately:

- Are you learning AWS for a current job requirement?
- Is this for freelance work or a specific client project?
- Could AWS skills lead to a salary increase or new opportunities?
- What's the approximate financial impact if you had this skill?
```

---

## Validation Checklist

- [ ] AI uses full 0-100 range (not clustering 50-70)
- [ ] AI asks clarifying questions when user context unclear
- [ ] Same task scores differently for different user contexts
- [ ] Low-value tasks (< 30) are identified and surfaced clearly
- [ ] High-value tasks (> 80) show strong scores across multiple dimensions
- [ ] Financial dimension tied to actual $ amounts
- [ ] Knowledge dimension considers user's current skills
- [ ] Strategic dimension requires explicit goal alignment

## Benefits

1. **Prevents clustering**: Multi-dimensional scoring forces differentiation
2. **Personalization**: Scores reflect individual user situation
3. **Strategic focus**: Long-term value weighted equally with short-term gains
4. **Financial clarity**: Explicit $ anchors prevent vague "impact" scoring
5. **Learning recognition**: Knowledge development properly valued
6. **Better decisions**: Low-value work surfaces clearly for skipping

## Migration Notes

- **Existing tasks**: Will continue working with old 0-10 scores (no breaking change)
- **New tasks**: Will use 0-100 scale with 3D framework
- **Priority calculation**: `priority = llm_value / duration_min` still works
- **Higher absolute values**: 0-100 scale produces higher priority numbers (expected)

## Next Steps

1. **Test with real user interactions**: Monitor clarification question usage
2. **Validate score distribution**: Check if scores spread across 0-100 range
3. **Gather feedback**: Does personalization feel accurate?
4. **Iterate anchors**: Adjust $ amounts if needed for different user contexts
5. **Add user profile**: Consider storing user context (income, goals, skills) for repeated scoring

## Research Basis

- **RICE Framework**: Multi-dimensional decomposition prevents clustering
- **Eisenhower Matrix**: Separates importance from urgency
- **Prompt Engineering Research** (2024-2025):
  - XML structuring reduces errors
  - Explicit anchoring improves calibration
  - Multi-dimensional scoring prevents regression to mean
  - Clarification protocols improve personalization

## References

- Wei et al. (2022) - Chain-of-Thought Prompting
- Wang et al. (2022) - Self-Consistency Improves Reasoning
- Schulhoff et al. (2025) - The Prompt Report: Systematic Survey
- RICE Scoring Model - Product prioritization framework
- Eisenhower Matrix - Important vs. Urgent distinction
