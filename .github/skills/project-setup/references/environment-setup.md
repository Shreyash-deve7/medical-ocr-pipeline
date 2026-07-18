# Environment Setup

Configure development, testing, and production environments with proper separation and security.

## Environment Detection

### Node.js Projects
```bash
# Detect Node.js version
node --version
# Detect package manager
npm --version || yarn --version || pnpm --version
```

### Python Projects
```bash
# Detect Python version
python --version
# Detect virtual environment
python -m venv venv
# Detect pip version
pip --version
```

### Java Projects
```bash
# Detect Java version
java -version
# Detect Maven/Gradle
mvn --version || gradle --version
```

## Environment Configuration

### Node.js (.env files)
```bash
# .env.development
PORT=3000
DATABASE_URL=postgresql://localhost:5432/dev_db
NODE_ENV=development

# .env.test
PORT=3001
DATABASE_URL=postgresql://localhost:5432/test_db
NODE_ENV=test

# .env.production
PORT=3000
DATABASE_URL=postgresql://prod-db:5432/prod_db
NODE_ENV=production
```

### Python (.env files)
```bash
# .env.development
export DATABASE_URL=postgresql://localhost:5432/dev_db
export DEBUG=true
export SECRET_KEY=dev-secret-key

# .env.test
export DATABASE_URL=postgresql://localhost:5432/test_db
export DEBUG=false
export SECRET_KEY=test-secret-key

# .env.production
export DATABASE_URL=postgresql://prod-db:5432/prod_db
export DEBUG=false
export SECRET_KEY=prod-secret-key
```

### Docker Compose
```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=development
      - DATABASE_URL=postgresql://postgres:password@db:5432/app
    volumes:
      - .:/app
      - /app/node_modules

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=app
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    ports:
      - "5432:5432"
```

## Environment-Specific Configuration

### Development
- Local databases (SQLite, local PostgreSQL)
- Debug mode enabled
- Hot reload/reload capabilities
- Local file storage
- Verbose logging

### Testing
- In-memory databases (SQLite in memory)
- Mock external services
- Fast execution
- Isolated test environment
- Coverage reporting

### Production
- Managed databases (AWS RDS, Azure SQL)
- Debug mode disabled
- Optimized performance
- Cloud storage
- Structured logging

## Environment Validation

### Node.js
```bash
# Validate environment variables
node -e "require('dotenv').config(); console.log('PORT:', process.env.PORT)"

# Check database connection
node -e "
const { Pool } = require('pg');
const pool = new Pool({ connectionString: process.env.DATABASE_URL });
pool.query('SELECT 1').then(() => console.log('Database connected')).catch(err => console.error('Database connection failed:', err));
"
```

### Python
```bash
# Validate environment variables
python -c "from dotenv import load_dotenv; load_dotenv(); print('DATABASE_URL:', os.getenv('DATABASE_URL'))"

# Check database connection
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
import psycopg2
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
print('Database connected')
conn.close()
"
```

## Best Practices

- **Never commit .env files** to version control
- **Use environment-specific configuration** files
- **Validate environment variables** at startup
- **Separate secrets** from configuration
- **Use Docker for consistency** across environments
- **Document environment setup** in README

## Anti-patterns

- Hardcoding environment variables in code
- Using the same .env file for all environments
- Skipping environment validation
- Committing .env files to Git
- Using local databases in production
- Not separating development and testing environments
