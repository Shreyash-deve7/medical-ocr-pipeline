# TypeScript JSDoc

JSDoc is the standard for documenting TypeScript/JavaScript code. Keep it simple, consistent, and machine-readable.

## Basic Structure

```typescript
/**
 * Brief description ending with a period.
 *
 * Longer explanation if needed.
 *
 * @param {string} categoryId - The category to filter by.
 * @param {number} [page=1] - Page number (1-indexed).
 * @param {number} [limit=20] - Maximum items per page.
 * @returns {Promise<ProductPage>} Resolves to a page of product records.
 * @throws {NotFoundError} If the category does not exist.
 *
 * @example
 * const page = await fetchProducts('electronics', 2, 10);
 * console.log(page.items);
 */
async function fetchProducts(
  categoryId: string,
  page = 1,
  limit = 20
): Promise<ProductPage> { ... }
```

## Tag Reference

| Tag | Purpose | Example |
|-----|---------|---------|
| `{@param name type}` | Parameter with type | `{@param {string} categoryId}` |
| `{@param {type} name}` | Alternative syntax | `{@param {string} categoryId}` |
| `{@type name}` | Type annotation for param | `{@type {string} categoryId}` |
| `{@returns}` | Return value description | `{@returns {Promise<ProductPage>}}` |
| `{@throws}` | Exception thrown | `{@throws {NotFoundError}}` |
| `{@example}` | Code example | `{@example const page = await fetchProducts(...);}` |
| `{@link}` | Cross-reference | `{@link https://example.com}` |
| `{@see}` | See also | `{@see fetchProducts}` |

## Best Practices

- **One-line summary**: End with a period.
- **Blank line**: Separate summary from details.
- **Order**: Params → Returns → Throws → Examples → See/See also.
- **Types**: Include types for all params and returns.
- **Optional params**: Mark with `[name=default]` in tag and optional in signature.
- **Examples**: Include runnable examples; they become part of the documentation.
- **Consistency**: Use `{@param}` consistently; avoid mixing `{param}`.

## Validation

After writing JSDoc, run TypeScript compiler to ensure types are correct:

```bash
tsc --noEmit
```

## Anti-patterns

- Missing types: `{@param categoryId}` vs `{@param {string} categoryId}`
- Inconsistent ordering: Returns before Params.
- Overly verbose examples: Include only what's necessary to demonstrate usage.
- Using `@description` (not a valid JSDoc tag).
- Mixing JSDoc with HTML-style comments (`/** ... */` is correct).
