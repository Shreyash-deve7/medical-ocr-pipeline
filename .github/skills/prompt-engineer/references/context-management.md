# Context Management

LLMs attend unevenly across the context window. Manage what goes where to protect the most important information.

## Attention Budget

Models weight positions differently:
- **Start** (primacy): strong recall — put core instructions and the system prompt here.
- **End** (recency): strong recall — put the current task, the question, and few-shot examples' final item here.
- **Middle** (lost-in-the-middle): weakest recall — long reference material placed here is often ignored.

Implication: keep instructions at the top, the live query at the bottom, and treat the middle as "bulk storage, not control flow."

## Degradation Patterns

- **Lost-in-the-middle**: key facts in long context get overlooked. Symptom: model ignores a constraint stated mid-document.
- **Context fatigue**: as context grows, adherence to early instructions can slip. Symptom: early format rules violated late in a long session.
- **Distraction**: irrelevant context dilutes focus. Symptom: model answers using the wrong source among many.
- **Truncation**: inputs exceeding the window are cut — usually from the start or middle. Symptom: missing the system prompt or early examples.

## Optimization Strategies

- **Compress**: summarize or retrieve only the relevant chunk instead of dumping everything.
- **Reorder**: put instructions first, query last; move reference material to the middle deliberately.
- **Chunk & retrieve (RAG)**: don't prepend the whole knowledge base — retrieve the top-k relevant passages per query.
- **Recency refresh**: repeat critical constraints near the end if the context is long.
- **Prune conversation**: drop or summarize stale turns in multi-turn sessions to stay under budget.
- **Set boundaries**: cap retrieved tokens; enforce a max context size per call.

## Multi-turn Sessions

- Summarize the conversation periodically rather than carrying full history.
- Re-state the standing task and constraints every N turns to counter fatigue.
- Keep the system prompt stable and cached; vary only the user turn.

## Monitoring

- Track prompt length over time; alert when it approaches the model's limit.
- Log cases where the model ignored a stated constraint — a sign of degradation.
- A/B test context ordering (instructions-first vs. interleaved) on your task.

## Anti-patterns
- Prepending an entire document when only a section is relevant.
- Burying the key instruction in the middle of a long prompt.
- Letting multi-turn history grow unbounded.
- Assuming more context always helps — often it hurts.
