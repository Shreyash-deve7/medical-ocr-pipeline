# Coverage Reports

Generate and interpret documentation coverage to ensure completeness and maintainability.

## Tools

- **Python**: `pytest --cov=module` (pytest-cov), `coverage run -m pytest`
- **JavaScript/TypeScript**: `jest --coverage`, `c8 run test`
- **OpenAPI**: `npx @redocly/cli lint openapi.yaml`, `swagger-cli validate`

## Report Formats

### Textual (console)
```bash
# Python
pytest --cov=myproject --cov-report=term

# JS/TS
jest --coverage --coverageReporters=text
```

### HTML
```bash
# Python
pytest --cov=myproject --cov-report=html
# Open browser: htmlcov/index.html

# JS/TS
jest --coverage --coverageReporters=html
# Open index.html in coverage folder
```

### JSON (for CI dashboards)
```bash
# Python
pytest --cov=myproject --cov-report=json

# JS/TS
jest --coverage --coverageReporters=json
```

## Interpreting Coverage

| Coverage % | Assessment |
|------------|------------|
| < 60% | Poor — prioritize undocumented functions, edge cases, error paths. |
| 60–80% | Acceptable — focus on public API and error conditions. |
| 80–95% | Good — ensure examples and integration tests are solid. |
| > 95% | Excellent — consider trimming low-value docstrings. |

## Best Practices

- **Include examples**: Docstring examples should be tested (doctest, integration tests).
- **Document public API**: All functions/classes exposed to users.
- **Document exceptions**: List all possible exceptions with conditions.
- **Keep it maintainable**: Avoid over-documenting trivial getters/setters.
- **Automate**: Add coverage checks to CI; fail if coverage drops.

## Anti-patterns

- Ignoring uncovered edge cases.
- Skipping error path documentation.
- Using coverage as the sole measure of documentation quality.
- Not updating coverage after refactoring.
- Relying on console output only; generate HTML for review.
