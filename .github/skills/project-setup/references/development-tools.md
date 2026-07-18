# Development Tools

Set up IDE plugins, linters, formatters, and development tools for improved productivity and code quality.

## IDE Configuration

### VS Code Extensions
```json
// .vscode/extensions.json
{
  "recommendations": [
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "editorconfig.editorconfig",
    "ms-python.python",
    "redhat.java",
    "vscjava.vscode-java-debugger",
    "ms-dotnettools.csharp",
    "github.copilot",
    "eamodio.gitlens",
    "streetsidesoftware.code-spell-checker",
    "johnsoncodehk.volar",
    "vue.volar",
    "bierner.markdown-preview-github-styles",
    "shd101wyy.markdown-preview-github-styles",
    "pkief.material-icon-theme",
    "ms-vscode.live-server",
    "formulahendry.dotnet-test-explorer",
    "ms-python.black",
    "ms-python.isort",
    "njp00233.python-type-hint-comments",
    "visualstudioexptteam.vscodeintellicode",
    "ms-vscode.cpptools",
    "llvm-vs-code-extensions.vscode-clangd",
    "github.copilot-chat",
    "eamodio.gitlens",
    "donjayamanne.githistory",
    "mhutchie.git-graph",
    "alefragnani.bookmarks",
    "stkb.rewrap",
    "oderwat.indent-rainbow",
    "wix.vscode-import-cost",
    "christian-kohler.path-explorer",
    "fabiospampinato.vscode-open-in-editor",
    "eamodio.gitlens",
    "donjayamanne.githistory",
    "mhutchie.git-graph",
    "alefragnani.bookmarks",
    "stkb.rewrap",
    "oderwat.indent-rainbow",
    "wix.vscode-import-cost",
    "christian-kohler.path-explorer",
    "fabiospampinato.vscode-open-in-editor"
  ]
}
```

### IntelliJ IDEA Plugins
```xml
<!-- .idea/plugins.xml -->
<idea-plugin>
  <id>com.intellij.plugins</id>
  <name>Plugin Name</name>
  <version>1.0.0</version>
</idea-plugin>
```

## Linting and Formatting

### Node.js (ESLint/Prettier)
```javascript
// .eslintrc.js
module.exports = {
  env: {
    browser: true,
    node: true,
    es2021: true,
  },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react/recommended',
    'plugin:react-hooks/recommended',
    'prettier',
  ],
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  plugins: [
    '@typescript-eslint',
    'react',
    'react-hooks',
    'prettier',
  ],
  rules: {
    'prettier/prettier': 'error',
    'react/react-in-jsx-scope': 'off',
    'no-unused-vars': 'error',
    'no-console': 'warn',
  },
};
```

```javascript
// .prettierrc.js
module.exports = {
  semi: true,
  singleQuote: true,
  trailingComma: 'all',
  printWidth: 80,
  arrowParens: 'avoid',
};
```

### Python (Black/isort)
```toml
# pyproject.toml
tool.black.line-length = 88
tool.black.target-version = ['py38']
tool.isort.profile = "black"
tool.isort.line-length = 88
```

### Java (Spotless)
```groovy
// gradle.properties
spotless {
  java {
    target fileTree('src/main/java')
    googleJavaFormat()
    indentWidth 2
    continuationIndentWidth 4
    endOfLine 'UNIX'
  }
}
```

## Development Server

### Node.js (Vite)
```javascript
// vite.config.js
import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 3000,
    open: true,
    proxy: {
      '/api': {
        target: 'http://localhost:3001',
        changeOrigin: true,
      },
    },
  },
});
```

### Python (FastAPI)
```python
# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Hello World"}
```

## Debugging Tools

### Node.js (Debugger)
```javascript
// debug.js
const server = require('http').createServer((req, res) => {
  // Add breakpoints here
  debugger;
  res.end('Hello World');
});

server.listen(3000, () => {
  console.log('Server running on port 3000');
});
```

```bash
# Run with debugger
node --inspect-brk debug.js
```

### Python (Debugger)
```python
# debug.py
import pdb

def calculate_sum(a, b):
    pdb.set_trace()  # Breakpoint
    return a + b

result = calculate_sum(5, 10)
print(f"Result: {result}")
```

```bash
# Run with debugger
python -m pdb debug.py
```

## Task Runners

### Node.js (npm scripts)
```json
// package.json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "test": "jest",
    "test:watch": "jest --watch",
    "lint": "eslint src/",
    "format": "prettier --write src/",
    "type-check": "tsc --noEmit",
    "deploy": "npm run build && pm2 start ecosystem.config.js --env production"
  }
}
```

### Python (Poetry scripts)
```toml
# pyproject.toml
tool.poetry.scripts = {
  "dev" = "uvicorn main:app --reload",
  "build" = "python -m build",
  "test" = "pytest",
  "lint" = "flake8 src/",
  "format" = "black src/",
  "type-check" = "mypy src/",
  "deploy" = "uvicorn main:app --host 0.0.0.0 --port 8000"
}
```

## Best Practices

- **Use consistent formatting** across the team
- **Set up linting rules** for code quality
- **Configure debugging tools** for efficient debugging
- **Automate repetitive tasks** with scripts
- **Use environment-specific configurations**
- **Document development setup**
- **Version control IDE settings**
- **Use pre-commit hooks**

## Anti-patterns

- Hardcoding development settings
- Skipping linting/formatting
- Not setting up debugging tools
- Not automating repetitive tasks
- Not documenting development setup
- Not version controlling IDE settings
- Using inconsistent formatting
- Not using pre-commit hooks
- Ignoring type checking
- Not setting up environment-specific configurations
