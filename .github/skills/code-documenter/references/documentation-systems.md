# Documentation Systems

Choose the right documentation system for your project. Static sites are most common; interactive docs are powerful for APIs.

## Static Site Generators

### Docusaurus
```bash
npm install -g docusaurus-init
docusaurus-init
```
- Markdown-based, supports code blocks, search, i18n.
- Great for docs-heavy projects (React, Python, etc.).

### MkDocs
```bash
pip install mkdocs mkdocs-material
mkdocs new my-project
mkdocs serve
```
- Simple, YAML-based config.
- Material theme looks professional.

### VitePress
```bash
npm init vitepress
vitepress dev docs
```
- Vite-powered, fast builds.
- Markdown + Vue components.

## Interactive API Docs

### OpenAPI 3.1 + Swagger UI
```yaml
# swagger.yaml
servers:
  - url: http://localhost:3000/api
paths:
  /users/{id}:
    get:
      summary: Get user by ID
      operationId: getUserById
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: integer
      responses:
        '200':
          description: User found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/User'
```

```typescript
// server.ts
import swaggerUi from 'swagger-ui-express';
import yaml from 'yamljs';
app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(yaml.load('./swagger.yaml')));
```

### Redoc
```typescript
import Redoc from 'redoc-express';
app.use('/docs', Redoc({ specUrl: '/openapi.yaml' }));
```

### GraphQL + GraphiQL/Altair
```typescript
import { GraphQLSchema, GraphQLObjectType, GraphQLString } from 'graphql';
const schema = new GraphQLSchema({ ... });
app.use('/graphql', graphqlHTTP({ schema }));
```

## Best Practices

- **Version docs**: Keep docs in sync with code versions.
- **Search**: Enable full-text search (Docusaurus, MkDocs).
- **Code examples**: Use live code tabs (Docusaurus, VitePress).
- **API reference**: Auto-generate from OpenAPI/GraphQL.
- **User guides**: Separate from API reference.

## Anti-patterns

- Manual docs for large APIs (auto-generate from spec).
- No search functionality.
- Docs not versioned.
- Mixing static and interactive docs without clear separation.
