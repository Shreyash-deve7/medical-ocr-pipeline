# Dependency Management

Set up package managers, version control, and dependency resolution for different project types.

## Package Manager Setup

### Node.js (npm/yarn/pnpm)
```bash
# Initialize npm project
npm init -y

# Install dependencies
npm install
npm install package-name
npm install package-name@version

# Install dev dependencies
npm install --save-dev package-name

# Global installation (for CLI tools)
npm install -g package-name

# Yarn alternative
yarn init -y
yarn add package-name
yarn add package-name@version --dev

# Pnpm alternative
pnpm init
pnpm add package-name
pnpm add package-name@version --dev
```

### Python (pip/poetry/uv)
```bash
# Initialize poetry project
poetry init

# Install dependencies
poetry add package-name
poetry add package-name@version --dev

# Install from requirements.txt
pip install -r requirements.txt
pip install package-name
pip install package-name==version

# Modern alternative: uv
uv init
uv add package-name
uv add package-name@version --dev
```

### Java (Maven/Gradle)
```bash
# Maven
mvn archetype:generate -DgroupId=com.example -DartifactId=my-app -Dversion=1.0.0
mvn add dependency

# Gradle
gradle init --type java-application
gradle add dependency
```

### .NET (dotnet)
```bash
# Initialize project
dotnet new console -n MyApp

# Add package
dotnet add package Package.Name
```

## Version Control Setup

### Git Configuration
```bash
# Set up global git config
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Set up repository
git init
git add .
git commit -m "Initial commit"

# Create .gitignore
# Use template based on project type
# Node.js
echo "node_modules/" >> .gitignore
echo ".env" >> .gitignore
echo "dist/" >> .gitignore
echo "build/" >> .gitignore

# Python
echo "__pycache__/" >> .gitignore
echo ".env" >> .gitignore
echo "*.pyc" >> .gitignore
echo "venv/" >> .gitignore

# Java
# .gitignore
echo "target/" >> .gitignore
echo ".idea/" >> .gitignore
echo "*.iml" >> .gitignore
```

### GitHub Actions
```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: [16, 18, 20]
    steps:
      - uses: actions/checkout@v3
      - name: Use Node.js ${{ matrix.node-version }}
        uses: actions/setup-node@v3
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'npm'
      - run: npm ci
      - run: npm test
```

## Dependency Locking

### Node.js
```bash
# npm
npm install --package-lock-only
# or
npm ci

# yarn
yarn lockfile v1
yarn install --mode frozen-lockfile

# pnpm
pnpm install --lockfile-only
pnpm install --frozen-lockfile
```

### Python
```bash
# poetry
poetry lock

# pip (requirements.txt)
pip freeze > requirements.txt

# uv
uv lock
uv sync
```

## Dependency Security

### Node.js
```bash
# Audit dependencies
npm audit
npm audit fix

# Check for known vulnerabilities
audit-ci --report-mode fail
```

### Python
```bash
# Check for vulnerabilities
safety check
pip-audit
```

## Best Practices

- **Use version ranges** when possible (e.g., `^1.2.3`)
- **Lock dependencies** for reproducible builds
- **Separate dev/prod dependencies**
- **Use semantic versioning**
- **Regular security audits**
- **Document dependency versions**

## Anti-patterns

- Hardcoding dependency versions
- Committing lock files to version control
- Skipping dependency audits
- Using global packages in projects
- Not separating dev and prod dependencies
- Ignoring dependency security vulnerabilities
