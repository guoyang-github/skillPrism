---
name: skill-name-kebab-case
description: >-
  One or two sentences describing what this API skill does, when to use it, and
  what the user gets back. Mention the service or API standard.
tool_type: api
primary_tool: rest
languages:
  - python
keywords:
  - keyword-one
  - keyword-two
  - keyword-three
---

# Skill Title

## When to Use

Describe the exact problem this skill solves and the input data/state expected.

## When NOT to Use

List cases where another skill or approach would be better.

## Quick Start

```python
import requests

url = "https://api.example.com/v1/resource"
headers = {"Authorization": "Bearer ${API_TOKEN}"}
params = {"limit": 10}

response = requests.get(url, headers=headers, params=params, timeout=30)
response.raise_for_status()
print(response.json())
```

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `api_token` | string | Yes | Authentication token stored in an environment variable |
| `params` | dict | No | Query or body parameters |

## Outputs

| Name | Type | Description |
|---|---|---|
| `response` | dict | Parsed JSON response from the API |

## Parameters Reference

| Parameter | Typical Values | Notes |
|---|---|---|
| `timeout` | 10-60 seconds | Request timeout |
| `retries` | 1-5 | Number of retries on transient failures |

## Common Pitfalls / Troubleshooting

- **Rate limiting**: implement exponential backoff and respect `Retry-After` headers.
- **Authentication leaks**: never log full tokens or credentials.
- **Timeouts**: set both connect and read timeouts explicitly.

## Performance & Resources

- Network latency dominates runtime; batch requests when the API supports it.
- Memory: usually low unless responses are very large.

## Security & Data Privacy

- Load API keys from environment variables or a secrets manager, never from code.
- Validate SSL certificates; do not disable verification in production.
- Sanitize user input before including it in URLs or payloads.

## References

1. Requests library documentation.

## Related Skills

- `api-batch-download`
- `api-error-handling`
