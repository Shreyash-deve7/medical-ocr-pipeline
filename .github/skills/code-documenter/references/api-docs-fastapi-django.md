# FastAPI / Django API Documentation

Choose the right strategy for your Python web framework. FastAPI generates OpenAPI specs automatically; Django needs manual docstrings or third-party tools.

## FastAPI (OpenAPI-first)

FastAPI automatically creates OpenAPI 3.0 specs. Add docstrings to functions and classes for better descriptions.

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class User(BaseModel):
    id: int
    name: str
    email: str

@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: int) -> User:
    """Retrieve a user by their unique identifier.

    Args:
        user_id: Positive integer identifying the user.

    Returns:
        User object with id, name, and email.

    Raises:
        HTTPException: If user is not found (404).
    """
    return User(id=user_id, name="Alice", email="alice@example.com")
```

**FastAPI-specific tips:**
- Use `response_model` for OpenAPI schema.
- Docstrings appear in Swagger UI and ReDoc.
- Use `Summary` and `Description` decorators for finer control.
- Include examples with `response_model_example`.

## Django REST Framework

DRF uses docstrings for API documentation. Use `drf-yasg` or `sphinx` for full docs.

```python
from rest_framework import serializers
from drf_yasg.utils import swagger_auto_schema

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email']

@swagger_auto_schema(
    method='get',
    responses={200: UserSerializer},
    operation_description='Retrieve a user by ID.'
)
@api_view(['GET'])
def get_user(request, user_id):
    """Get user details.

    Args:
        user_id: Integer primary key of the user.

    Returns:
        JSON serialized user data.

    Raises:
        Http404: If user does not exist.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise Http404
    serializer = UserSerializer(user)
    return Response(serializer.data)
```

**Django-specific tips:**
- Use `drf-yasg` or `sphinx` for interactive docs.
- Docstrings appear in generated OpenAPI/Swagger.
- Use `@swagger_auto_schema` for fine-grained control.
- Include `operation_description` and `responses`.

## Validation

Validate OpenAPI specs:

```bash
pip install openapi-spec-validator
python -c "from openapi_spec_validator import validate_spec; validate_spec('openapi.json')"
```

Or use Redocly CLI:

```bash
npx @redocly/cli lint openapi.yaml
```

## Anti-patterns

- Missing response_model in FastAPI.
- Using docstrings for everything (use decorators for Swagger details).
- Not validating OpenAPI spec after changes.
- Mixing Django and FastAPI styles in the same project.
