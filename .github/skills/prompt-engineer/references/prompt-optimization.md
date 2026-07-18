# Prompt Optimization

Iterative refinement to improve accuracy, consistency, and token efficiency. Change one variable at a time so you can attribute improvements.

## Iterative Refinement Loop

1. **Baseline**: run the current prompt on the test set, record metrics.
2. **Hypothesize**: pick one weakness (e.g., "fails on empty input", "too verbose").
3. **Change one thing**: add a constraint, reorder examples, tighten wording.
4. **Re-measure**: compare against baseline on the same cases.
5. **Keep or revert**: keep only if it improves or holds metrics at lower cost.
6. Repeat until accuracy target (≥80%) and token budget are met.

## Token Reduction Techniques

- **Cut filler**: remove "Please" / "As an AI" pleasantries that add no signal.
- **Tighten format specs**: "exactly 3 bullets, one sentence each" beats "summarize concisely."
- **Move static context to system prompt**: keep the user turn minimal; cache the system prompt when the provider supports it.
- **Trim few-shot count**: 3 strong examples often beat 8 weak ones.
- **Use delimiters**: `###` / XML tags make boundaries explicit so the model parses faster and more reliably.
- **Lower max_tokens** where output length is bounded.

## A/B Testing Prompts

- Hold the model, temperature, and test set fixed.
- Split test cases into A (prompt v1) and B (prompt v2); compare on the same metrics.
- For production, run both behind a flag and compare on real traffic (guardrail on cost).
- Report: accuracy delta, consistency (variance across runs), median tokens, latency p50/p95.

## Rewriting for Clarity

- Lead with the goal, then constraints, then format. Models weight the start and end most.
- Use imperative, unambiguous verbs: "Extract", "Classify", "Return".
- Replace vague adjectives ("relevant", "appropriate") with measurable criteria.
- State what NOT to do explicitly for guardrails.

## Model Migration

When moving a prompt between models (e.g., GPT-4 → Claude → Gemini):
- Re-run the full test set; do not assume parity.
- Adjust for capability differences (some models need more explicit CoT, others less).
- Re-tune temperature and max_tokens per model.
- Watch for format drift in structured outputs — re-validate the schema.

## Optimization Checklist

- [ ] One change per iteration, measured against baseline
- [ ] Token count reduced without accuracy loss
- [ ] Static context cached in system prompt
- [ ] Few-shot examples minimal and representative
- [ ] Format spec is explicit and bounded
- [ ] Re-tested on target model version
