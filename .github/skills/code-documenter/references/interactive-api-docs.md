# Interactive API Documentation

Interactive docs let users explore, test, and visualize APIs directly in the browser. Choose based on your API style.

## OpenAPI 3.1 + Swagger UI

### Setup
```bash
npm install swagger-ui-express yamljs
# or: npm install @swagger-api/swagger-ui-express
```

```typescript
// server.ts
import express from 'express';
import swaggerUi from 'swagger-ui-express';
import yaml from 'yamljs';

const app = express();
const swaggerSpec = yaml.load('./openapi.yaml');

// Serve Swagger UI at /api-docs
app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(swaggerSpec, {
  explorer: true,
  customCss: '.swagger-ui .topbar { display: none }',
  customSiteTitle: 'My API Docs',
}));
```

### Features
- **Try it out**: Test endpoints directly in the browser.
- **Models**: View and expand JSON schemas.
- **Authentication**: Support OAuth2, API keys, JWT.
- **Filtering**: Filter operations by tag.
- **Code samples**: Generate curl, Node.js, Python examples.

## Redoc

### Setup
```bash
npm install redoc-express
```

```typescript
// server.ts
import Redoc from 'redoc-express';

app.use('/docs', Redoc({
  title: 'My API',
  specUrl: '/openapi.yaml',
  scrollYOffset: 50,
  hideHostname: true,
  hideDownloadButton: true,
  expandResponses: '200,201',
  pathInMiddlePanel: true,
}));
```

### Features
- **Clean UI**: No interactive testing, just documentation.
- **Markdown support**: Use Markdown in spec for rich descriptions.
- **Mobile-friendly**: Responsive design.
- **Performance**: Lightweight, no client-side bundle.

## GraphQL + GraphiQL/Altair

### Setup
```bash
npm install graphql express-graphql graphql-playground-middleware
```

```typescript
// server.ts
import { graphqlHTTP } from 'express-graphql';
import { buildSchema } from 'graphql';

const schema = buildSchema(`
  type Query {
    hello: String
    user(id: Int!): User
  }
  type User {
    id: Int!
    name: String
    email: String
  }
`);

app.use('/graphql', graphqlHTTP({
  schema,
  graphiql: true, // or playground: true
  pretty: true,
}));
```

### Features
- **Introspection**: Explore schema automatically.
- **Queries**: Test GraphQL queries directly.
- **Variables**: UI for variables.
- **History**: Save and replay queries.

## gRPC + Protobuf Web

### Setup
```bash
npm install grpc-web protobufjs
```

```typescript
// client.ts
import { grpc } from '@improbable-eng/grpc-web';
import { HelloRequest, HelloService } from './hello_pb';

const client = new HelloServiceServiceClient('http://localhost:8080', null, null);
```

### Features
- **Type safety**: Generated TypeScript clients.
- **Streaming**: Bidirectional streaming support.
- **Authentication**: JWT, TLS.

## Best Practices

- **Secure docs**: Protect `/api-docs` or `/docs` endpoints.
- **Versioning**: Serve different spec versions by path (`/v1/docs`).
- **CI/CD**: Auto-generate and deploy docs with API changes.
- **SEO**: Add meta tags, Open Graph for API docs.
- **Branding**: Customize theme, logo, colors.

## Anti-patterns

- Hardcoding spec path in code (use environment variables).
- Not protecting interactive docs (anyone can see API).
- Using Swagger UI for simple REST APIs (overkill).
- Not versioning interactive docs (breaking changes cause confusion).
