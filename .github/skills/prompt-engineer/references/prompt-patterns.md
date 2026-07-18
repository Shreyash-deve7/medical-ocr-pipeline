# Prompt Patterns

Choose the right reasoning pattern for the task. Start simple (zero-shot) and escalate only when needed — more complex patterns cost more tokens and latency.

## Zero-shot
Direct instruction, no examples. Best for well-defined tasks the model already knows.

```
Classify the sentiment of the following review as Positive, Negative, or Neutral.

Review: {{review}}
Sentiment:
```
Use when: the task is common, the output format is simple, and you have a clear instruction. Cheapest option.

## Few-shot
Provide 2–5 input→output examples that match the target distribution. Improves reliability and format adherence.

```
Review: "The battery life is incredible, lasts all day."
Sentiment: Positive

Review: "Stopped working after two weeks. Very disappointed."
Sentiment: Negative

Review: {{review}}
Sentiment:
```
Rules:
- Examples must match the real input distribution (not toy cases).
- Examples must NOT contradict the instructions.
- Order matters less than relevance; put the most representative examples near the end (recency bias).
- Label examples consistently; mixed labeling confuses the model.

## Chain-of-Thought (CoT)
Prompt the model to reason step-by-step before answering. Use for math, logic, multi-step decisions.

```
Solve the problem step by step. Show your reasoning, then give the final answer.

Problem: {{problem}}
Reasoning:
Answer:
```
Variants:
- **Zero-shot CoT**: just add "Let's think step by step."
- **Self-consistency**: sample multiple reasoning paths, take the majority final answer (higher accuracy, higher cost).

## ReAct (Reason + Act)
Interleave reasoning with tool calls. Use when the model must query external systems.

```
You have access to these tools: [search, calculator].
Think about what to do, then act. Repeat until you can answer.

Question: {{question}}
Thought: ...
Action: search[...]
Observation: ...
Thought: ...
Answer: ...
```

## Tree-of-Thoughts (ToT)
Explore multiple reasoning branches, evaluate each, and backtrack. Use for complex planning/search problems where a single linear path is fragile. Higher cost; reserve for high-value tasks.

## Pattern Selection Guide

| Task type | Start with |
|-----------|-----------|
| Classification, extraction, simple generation | Zero-shot → Few-shot |
| Math, logic, multi-step | CoT |
| Needs live data / APIs | ReAct |
| Open-ended planning, search | ToT (sparingly) |

## Anti-patterns
- Few-shot examples that don't resemble production inputs.
- CoT for trivial tasks (wasted tokens).
- Inconsistent or contradictory examples.
- Stuffing too many examples (dilutes the instruction and burns context).
