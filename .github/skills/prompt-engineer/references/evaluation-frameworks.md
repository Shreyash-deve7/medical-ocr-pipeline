# Evaluation Frameworks

You cannot improve a prompt you cannot measure. Build a test set and quantitative metrics before optimizing.

## Build a Test Set

- **Size**: at least 20–50 cases for a meaningful signal; more for production.
- **Coverage**: include the target distribution plus edge cases:
  - Empty / null input
  - Unusual formats, typos, non-English
  - Adversarial or out-of-scope requests
  - Long vs. very short inputs
- **Golden answers**: store expected output (exact or rubric-scored) alongside each input.
- **Version it**: keep the test set in source control so comparisons are reproducible.

## Metrics

| Metric | What it measures | How |
|--------|------------------|-----|
| Accuracy | Correct vs. golden | Exact or normalized match |
| Consistency | Stability across runs | Run N times, measure variance |
| Format adherence | Matches required schema | Schema validation pass rate |
| Token cost | Efficiency | Median tokens per call |
| Latency | Speed | p50 / p95 response time |
| Hallucination rate | Fabricated content | Human or LLM-judge review |

## Automated Evaluation

- **Exact match / regex**: for classification and fixed formats.
- **LLM-as-judge**: use a strong model to score outputs against a rubric (1–5 scales). Provide the rubric explicitly and the golden answer as reference.
- **Embedding similarity**: for open-ended text where phrasing varies but meaning is fixed.
- **Schema validators**: JSON Schema / Pydantic for structured outputs.

## Evaluation Report Template

```
Prompt version: v2
Model: <name> @ temp <t>
Test set: 50 cases (incl. 10 edge cases)
Accuracy: 86% (baseline 72%)
Consistency: 0.91 (baseline 0.78)
Format adherence: 100%
Median tokens: 420 (baseline 610)
Failure patterns: 3 cases of empty-input mishandling (fixed in v3)
```

## Regression Gating

- Store the report with the prompt version.
- Block deployment if accuracy drops below the threshold (e.g., <80%) or consistency falls under 0.85.
- Re-run the suite on every prompt change (CI if possible).

## Anti-patterns
- Testing only on happy-path inputs.
- Judging by a single run (ignore variance).
- Using the same model as both generator and sole judge without a rubric.
- Treating "looks good" as a metric.
