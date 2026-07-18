# Build Configuration

Configure build tools, packaging, and optimization for different project types and deployment targets.

## Build Tool Setup

### Node.js (Webpack/Vite/Rollup)
```javascript
// webpack.config.js
const path = require('path');

module.exports = {
  entry: './src/index.js',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.js',
    clean: true,
  },
  module: {
    rules: [
      {
        test: /\\.js$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-env'],
          },
        },
      },
    ],
  },
  optimization: {
    usedExports: true,
    sideEffects: false,
  },
  performance: {
    maxAssetSize: 500000,
    hints: 'warning',
  },
};
```

### Vite Configuration
```javascript
// vite.config.js
import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    rollupOptions: {
      external: [],
    },
  },
  server: {
    port: 3000,
    open: true,
  },
  optimizeDeps: {
    include: ['axios', 'lodash'],
  },
});
```

### Python (Poetry/pyproject.toml)
```toml
# pyproject.toml
[tool.poetry]
name = "my-project"
version = "0.1.0"
description = "A Python project"
authors = ["Your Name <your.email@example.com>"]

[tool.poetry.dependencies]
python = "^3.8"
requests = "^2.28"
fastapi = "^0.95"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4"
black = "^23.3"
flake8 = "^6.0"

[tool.poetry.scripts]
my-command = "my_module:main"
```

### Java (Maven/Gradle)
```xml
<!-- pom.xml (Maven) -->
<project>
  <build>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-compiler-plugin</artifactId>
        <version>3.11.0</version>
        <configuration>
          <source>17</source>
          <target>17</target>
        </configuration>
      </plugin>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-jar-plugin</artifactId>
        <version>3.3.0</version>
        <configuration>
          <archive>
            <manifest>
              <addClasspath>true</addClasspath>
            </manifest>
          </archive>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
```

## Packaging Configuration

### Docker
```dockerfile
# Dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
EXPOSE 3000
CMD ["npm", "start"]
```

```yaml
# docker-compose.yml
development:
  build:
    context: .
    dockerfile: Dockerfile.dev
  volumes:
    - ./src:/app/src
    - /app/node_modules
  ports:
    - "3000:3000"
  environment:
    - NODE_ENV=development

production:
  build:
    context: .
    dockerfile: Dockerfile
  ports:
    - "3000:3000"
  environment:
    - NODE_ENV=production
```

### Kubernetes
```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  labels:
    app: my-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
      - name: my-app
        image: my-app:latest
        ports:
        - containerPort: 3000
        env:
        - name: NODE_ENV
          value: "production"
        resources:
          limits:
            cpu: 500m
            memory: 512Mi
          requests:
            cpu: 250m
            memory: 256Mi
```

## Build Optimization

### Node.js
```javascript
// webpack.config.js (optimization)
module.exports = {
  optimization: {
    splitChunks: {
      chunks: 'all',
      minSize: 0,
      minChunks: 2,
    },
    runtimeChunk: 'single',
    removeAvailableModules: false,
    removeEmptyChunks: true,
    mergeDuplicateChunks: true,
    flagIncludedChunks: true,
    occurrenceOrder: true,
    sideEffects: true,
  },
};
```

### Python
```toml
# pyproject.toml (optimization)
[tool.poetry.scripts]
lint = "flake8 src/"
format = "black src/"
test = "pytest"
coverage = "pytest --cov=src --cov-report=html"
```

## CI/CD Integration

### GitHub Actions
```yaml
# .github/workflows/build.yml
name: Build and Test

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'
      - run: npm ci
      - run: npm run build
      - run: npm test
      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: build-output
          path: dist/
```

## Best Practices

- **Use build caching** for faster builds
- **Separate dev/prod builds**
- **Optimize bundle sizes**
- **Use environment-specific configs**
- **Validate build outputs**
- **Automate deployment**

## Anti-patterns

- Hardcoding build paths
- Skipping build validation
- Not separating dev/prod builds
- Ignoring bundle size optimization
- Not using build caching
- Committing build outputs to version control
