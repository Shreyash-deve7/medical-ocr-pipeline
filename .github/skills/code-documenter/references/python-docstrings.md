# Python Docstrings

Choose the right docstring style for your project. Google style is the most common; NumPy/Sphinx are popular in scientific and data-science projects.

## Google Style (PEP 257)

```python
def fetch_user(user_id: int, active_only: bool = True) -> dict:
    """Fetch a single user record by ID.

    Args:
        user_id: Unique identifier for the user.
        active_only: When True, raise an error for inactive users.

    Returns:
        A dict containing user fields (id, name, email, created_at).

    Raises:
        ValueError: If user_id is not a positive integer.
        UserNotFoundError: If no matching user exists.
    """
```

**Rules:**
- One-line summary ending with a period.
- Blank line after summary.
- Sections in order: Args, Returns, Raises (if any).
- Use imperative mood for Args/Returns.
- Parameter types in `Args:` are optional but recommended.
- Include exceptions in `Raises:`.

## NumPy Style

```python
def compute_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Parameters
    ----------
    vec_a : np.ndarray
        First input vector, shape (n,).
    vec_b : np.ndarray
        Second input vector, shape (n,).

    Returns
    -------
    float
        Cosine similarity in the range [-1, 1].

    Raises
    ------
    ValueError
        If vectors have different lengths.
    """
```

**Rules:**
- One-line summary ending with a period.
- Blank line after summary.
- Sections: Parameters, Returns, Raises.
- Use `type : description` format.
- Include type annotations in the signature.

## Sphinx Style

```python
def process_data(data: List[int], threshold: float = 0.5) -> Dict[str, Any]:
    """Process input data and return filtered results.

    :param data: List of integers to process.
    :param threshold: Minimum value to include in results (0.0–1.0).
    :type threshold: float
    :returns: Dictionary with keys 'count' and 'sum'.
    :rtype: dict
    :raises ValueError: If threshold is outside [0.0, 1.0].
    """
```

**Rules:**
- One-line summary ending with a period.
- Blank line after summary.
- Sections: `:param name: description`, `:type name: type`, `:returns: description`, `:rtype: type`, `:raises Exception: description`.
- Can mix with Google/NumPy in the same project (Sphinx supports both).

## Best Practices

- **Be concise**: One line summary; keep descriptions short but complete.
- **Use consistent style**: Pick one per module/project.
- **Include types**: Even if optional, they help IDEs and tools.
- **Document exceptions**: List all possible exceptions with conditions.
- **Avoid self-documenting getters**: Skip docstrings for simple property getters.
- **Use examples**: Include doctest blocks for critical functions.
- **Keep formatting**: Use standard indentation (4 spaces) and line breaks.

## Validation

After writing docstrings, run doctests to ensure examples work:

```bash
python -m doctest mymodule.py
pytest --doctest-modules mymodule.py
```

## Anti-patterns

- Vague descriptions: "Does something." → "Fetch user by ID."
- Missing parameter types: `user_id: int` vs `user_id: Unique identifier`
- Inconsistent ordering: Args before Returns, then Raises.
- Over-documenting trivial functions (e.g., `def __init__(self): pass`).
- Using markdown-style lists inside docstrings (use plain text).
