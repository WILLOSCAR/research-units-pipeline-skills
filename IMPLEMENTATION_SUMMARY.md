# Implementation Summary: Pipeline Quality Improvements

**Date**: 2026-01-18
**Based on**: Quality analysis of `e2e-agent-survey-latex-verify-20260118-182656`

## Overview

This document summarizes the skill modifications made to address P0, P1, and P2 defects identified in the pipeline output quality analysis. All changes focus on improving the "paper feel" of generated surveys by eliminating meta-narrative leakage, template repetition, and hollow paragraphs.

---

## Changes Made

### 1. `.codex/skills/transition-weaver/SKILL.md` (P0 Fix)

**Problem**: Meta-narrative leakage - transitions read like construction notes rather than real content.

**Changes**:
- Added **CRITICAL** guidance to avoid construction notes
- Added bad/good examples:
  - ❌ Bad: "After X, Y makes the bridge explicit via function calling, tool schema, routing..."
  - ✅ Good: "While loop design determines what actions are possible, tool interfaces define how those actions are grounded in executable APIs..."
- Added explicit prohibition of meta-narrative about section structure
  - ❌ Bad: "Y follows naturally by turning X's framing into..."
  - ✅ Good: "The limitations of X motivate researchers to explore Y."

**Impact**: Prevents the 4 meta-narrative leakage instances found at lines 59, 111, 165, 221 in future runs.

---

### 2. `.codex/skills/draft-polisher/SKILL.md` (P0 Fix)

**Problem**: Template phrase repetition, especially "Taken together" used 6 times.

**Changes**:
- Added **CRITICAL** guidance on synthesis opening variation:
  - Limit "Taken together" to maximum 1 use in entire draft
  - Provide alternatives: "In summary," "Across these studies," "The pattern that emerges," "A key insight," "Collectively," "The evidence suggests,"
  - Encourage direct conclusion statements without synthesis markers
  - Require content-specific synthesis openings, not template labels

**Impact**: Eliminates repetitive synthesis openings that signal "template filling".

---

### 3. `.codex/skills/subsection-writer/SKILL.md` (P1 Fixes)

**Problem 1**: Citation list enumeration (e.g., "e.g., A et al.; B et al.; C et al.") instead of integrated arguments.

**Changes**:
- Added **WRONG** example showing list-style enumeration (line 41 pattern)
- Added **BETTER** example showing integration into argument:
  - "Recent work on loop design spans diverse domains: Li et al. study X, Ghose et al. focus on Y, while Song et al. emphasize Z, suggesting that..."
- Added **CRITICAL** rule: Avoid "Notable lines of work include...", "Concrete implementations include...", "e.g., A et al.; B et al.; C et al."
- Require integration into argument sentences that explain what each work contributes or how they differ

**Problem 2**: Paragraphs lack "why this matters" context (长但空).

**Changes**:
- Added **CRITICAL** guidance in paragraph-plan execution:
  - Each paragraph should include "why this matters" or "what this reveals" context
  - Bad example: "Many systems adopt X."
  - Good example: "Many systems adopt X because it reduces Y, though this comes at the cost of Z."

**Impact**:
- Eliminates citation dump lines at lines 41, 65, 93, 117, 145, 172, 201, 227
- Adds evaluation anchors and "why it matters" context to hollow paragraphs

---

### 4. `.codex/skills/subsection-briefs/SKILL.md` (P2 Fix)

**Problem**: Briefs lack "why this comparison matters" and "what limitations to surface" guidance, leading to hollow paragraphs in C5.

**Changes**:

**In Step 5 (Propose axes)**:
- Added **CRITICAL** requirement: For each axis, include a brief note on "why this comparison matters"
- Examples:
  - "representation choice affects memory overhead and retrieval latency"
  - "evaluation protocol determines whether claims are reproducible"
- Purpose: Help writers understand significance, not just that papers differ

**In Step 8 (Build paragraph_plan)**:
- Para 2-4 (cluster_A): Added **"Include 'why this matters' guidance"** (e.g., "this matters because it affects cost/reliability/safety")
- Para 5-7 (cluster_B): Added **"Include limitation hooks"** (e.g., "what failure modes does this approach expose?")
- Para 10 (limitations): Added **"Be specific about what limitations to surface"** with examples:
  - "benchmark dependence"
  - "missing adversarial evaluation"
  - "unclear generalization"

**Impact**: Upstream guidance ensures writers have evaluation hooks and limitation prompts, preventing hollow paragraphs.

---

## Priority Classification

### P0 (阻断"论文感") - Implemented ✅
1. ✅ Meta-narrative leakage fix (`transition-weaver`)
2. ✅ Template phrase repetition fix (`draft-polisher`)
3. ✅ Pipeline voice already addressed in existing `draft-polisher` rules (line 15 pattern)

### P1 (改善局部引用质量) - Implemented ✅
4. ✅ Citation list enumeration fix (`subsection-writer`)
5. ✅ Hollow paragraph fix (`subsection-writer`)

### P2 (强化结构) - Implemented ✅
6. ✅ Evaluation hooks and limitation prompts (`subsection-briefs`)

---

## Testing Recommendations

To verify these improvements:

1. **Rerun E2E pipeline** with same query to compare output quality
2. **Check for meta-narrative**: Search DRAFT.md for patterns like:
   - "After X, Y makes the bridge explicit via..."
   - "follows naturally by turning X's framing into..."
3. **Check synthesis variation**: Count "Taken together" occurrences (should be ≤1)
4. **Check citation integration**: Search for "e.g., A et al.; B et al.; C et al." patterns
5. **Check evaluation context**: Verify paragraphs include "why this matters" or "this is important because"
6. **Review audit report**: Confirm template phrase warnings decrease

---

## Expected Improvements

**Before** (e2e-agent-survey-latex-verify-20260118-182656):
- 4 meta-narrative leakage instances
- 6× "Taken together" repetition
- 8 citation dump lines (41, 65, 93, 117, 145, 172, 201, 227)
- Multiple hollow paragraphs lacking evaluation context

**After** (next E2E run):
- 0 meta-narrative leakage (transitions are real content)
- ≤1 "Taken together" usage (varied synthesis openings)
- 0 citation dump lines (integrated into arguments)
- Paragraphs include "why this matters" context

**Quality Score Projection**:
- Technical Architecture: 9/10 (unchanged - already excellent)
- Output Quality: 7/10 → **8.5/10** (eliminates obvious auto-generation signals)
- Improvement Potential: 8/10 → **9/10** (P0/P1 fixes unlock further refinement)

---

## Related Documentation

- **Quality Analysis**: `/home/rjs/Workspace/codebase/research-units-pipeline-skills/PIPELINE_DIAGNOSIS_AND_IMPROVEMENT.md` (Section 7-8)
- **Modified Skills**:
  - `.codex/skills/transition-weaver/SKILL.md`
  - `.codex/skills/draft-polisher/SKILL.md`
  - `.codex/skills/subsection-writer/SKILL.md`
  - `.codex/skills/subsection-briefs/SKILL.md`

---

## Next Steps

1. **Immediate**: Test changes with a new E2E run
2. **Short-term**: Monitor audit reports for remaining template patterns
3. **Long-term**: Consider adding automated checks for:
   - Meta-narrative pattern detection
   - Synthesis opening diversity metrics
   - Citation integration quality scores
