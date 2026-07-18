# Structured Outputs

Force reliable, parseable results with JSON mode and function calling. Never trust free-form text when a schema is possible.

## JSON Mode

Instruct the model to return only JSON, then validate.

```
Return a JSON object with exactly these keys:
{
  "name": string,
  "age": integer,
  "tags": string[]
}
Respond with JSON only. No prose, no markdown fences.
```

Best practice:
- Provide the schema inline or via the provider's `response_format` / `json_schema` parameter.
- Validate the response with JSON Schema or Pydantic; on failure, retry or fall back.
- Strip markdown code fences defensively before parsing.

## Function Calling / Tool Use

Define typed functions the model can invoke.

```json
{
  "name": "create_ticket",
  "description": "Open a support ticket",
  "parameters": {
    "type": "object",
    "properties": {
      "title": { "type": "string" },
      "priority": { "type": "string", "enum": ["low", "medium", "high"] }
    },
    "required": ["title"]
  }
}
```
Rules:
- Write clear `description` fields — the model relies on them to choose the tool.
- Use `enum` to constrain categorical values.
- Mark only truly required fields as `required` to reduce friction.
- Handle the "no tool called" case explicitly.

## Schema Design Principles

- **Flat over nested** when possible — easier to validate and consume.
- **Enumerate** categorical outputs instead of free strings.
- **Bound lengths** (maxItems, maxLength) to control tokens and prevent runaway output.
- **Name clearly**: `user_id`, not `id` (ambiguous across objects).
- **Version schemas** alongside prompts; breaking changes need migration.

## Validation & Repair

1. Parse JSON; catch `JSONDecodeError`.
2. Run schema validation; collect all errors.
3. If invalid, retry with the error message appended ("Fix these: ...") or fall back to a safe default.
4. Log validation failures as evaluation signals (they reveal prompt gaps).

## Anti-patterns
- Asking for JSON in prose without `response_format` enforcement.
- Schemas with ambiguous or overlapping field meanings.
- Unbounded arrays that let the model emit huge outputs.
- Ignoring the possibility of malformed JSON in production.
