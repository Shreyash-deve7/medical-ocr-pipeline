# Testing Setup

Configure test frameworks, test data, and CI/CD integration for comprehensive testing.

## Test Framework Setup

### Node.js (Jest/Mocha/Chai)
```javascript
// jest.config.js
module.exports = {
  collectCoverageFrom: [
    'src/**/*.{js,jsx,ts,tsx}',
    '!src/**/*.d.ts',
    '!src/reportWebVitals.js',
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80,
    },
  },
  testMatch: [
    '<rootDir>/src/**/__tests__/**/*.{js,jsx,ts,tsx}',
    '<rootDir>/src/**/*.{spec,test}.{js,jsx,ts,tsx}',
  ],
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.js'],
  moduleNameMapping: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
};
```

### Python (pytest)
```python
# pytest.ini
[pytest]
testpaths = ["src"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "-v",
    "--tb=short",
    "--cov=src",
    "--cov-report=term-missing",
]
```

### Java (JUnit/Mockito)
```xml
<!-- pom.xml (Maven) -->
<properties>
  <junit.jupiter.version>5.9.1</junit.jupiter.version>
  <mockito.version>4.11.0</mockito.version>
</properties>

<dependencies>
  <dependency>
    <groupId>org.junit.jupiter</groupId>
    <artifactId>junit-jupiter-engine</artifactId>
    <version>${junit.jupiter.version}</version>
    <scope>test</scope>
  </dependency>
  <dependency>
    <groupId>org.mockito</groupId>
    <artifactId>mockito-junit-jupiter</artifactId>
    <version>${mockito.version}</version>
    <scope>test</scope>
  </dependency>
</dependencies>
```

## Test Data Management

### Node.js (Test Data)
```javascript
// fixtures/user.fixture.js
export const validUser = {
  id: 1,
  name: 'John Doe',
  email: 'john@example.com',
  createdAt: '2023-01-01T00:00:00Z',
};

export const invalidUser = {
  id: 'invalid',
  name: '',
  email: 'invalid-email',
};
```

### Python (Test Data)
```python
# fixtures/user_fixture.py
import pytest

@pytest.fixture
def valid_user():
    return {
        'id': 1,
        'name': 'John Doe',
        'email': 'john@example.com',
        'created_at': '2023-01-01T00:00:00Z',
    }

@pytest.fixture
def invalid_user():
    return {
        'id': 'invalid',
        'name': '',
        'email': 'invalid-email',
    }
```

## Test Configuration

### Environment Variables
```bash
# .env.test
DATABASE_URL=postgresql://localhost:5432/test_db
API_KEY=test-api-key
DEBUG=true
PORT=3001
```

### Test Coverage
```bash
# Node.js
npm run test:coverage
# Python
pytest --cov=src --cov-report=html
```

### Test Reports
```bash
# Node.js
npm run test:report
# Python
pytest --html=reports/test-report.html
```

## CI/CD Integration

### GitHub Actions
```yaml
# .github/workflows/test.yml
name: Test

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: [16, 18, 20]
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: password
        options: >
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'npm'
      - run: npm ci
      - run: npm test
      - name: Upload test results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: test-results-${{ matrix.node-version }}
          path: test-results/
```

## Test Best Practices

- **Write isolated tests** (no shared state)
- **Use test fixtures** for test data
- **Mock external dependencies**
- **Test error cases**
- **Use descriptive test names**
- **Maintain test coverage**
- **Automate test execution**

## Anti-patterns

- Hardcoding test data
- Skipping error case testing
- Sharing state between tests
- Not mocking external dependencies
- Ignoring test coverage
- Not automating test execution
- Writing flaky tests
- Not cleaning up test data
