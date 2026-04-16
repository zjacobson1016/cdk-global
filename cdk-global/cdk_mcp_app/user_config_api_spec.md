# User Config API — `/user-config`

Manages user configuration for the AIVA conversational AI interface (FAQs, swift settings).

**Base URL**: `https://api.fortellis.io/cdk-test/neuron/conversational-ai/interface/v1`

**Authentication**: OAuth 2.0 (Fortellis)

---

## Common Headers

All endpoints require:

| Header | Type | Required | Description |
|--------|------|----------|-------------|
| `Request-Id` | `string` (GUID) | Yes | Correlation ID unique per request |
| `Subscription-Id` | `string` | Yes | Fortellis Marketplace subscription identifier |
| `Department-Id` | `string` (GUID) | Yes | Unique ID for a specific department within a dealer |
| `Authorization` | `string` | Yes | OAuth 2.0 Bearer token from Fortellis authorization server |

---

## GET `/user-config`

Retrieve a user's saved configuration.

### Request Body

Array of objects:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | `string` | Yes | User ID |

**Example:**

```json
[
  {
    "user_id": "YUEYWUS67TY"
  }
]
```

### 200 — Success

Returns a plain-English response string.

```json
{
  "result": "In May 2023, you closed 50 ROs."
}
```

---

## POST `/user-config`

Create a new user configuration (store to database).

### Request Body

Array of objects:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | `string` | Yes | User ID |
| `enterprise_id` | `string` | Yes | Enterprise ID |
| `questions` | `string` | No | Questions separated by pipe (`\|`) |
| `is_swift` | `boolean` | No | Swift mode enabled |

**Example:**

```json
[
  {
    "user_id": "user_id",
    "enterprise_id": "e_id",
    "questions": "How many ROs did we close in May 2023?| How many appointments are there today?",
    "is_swift": true
  }
]
```

### 200 — Success

Returns a plain-English response string.

```json
{
  "result": "In May 2023, you closed 50 ROs."
}
```

---

## PUT `/user-config`

Update an existing user configuration.

### Request Body

Array of objects (same schema as POST):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | `string` | Yes | User ID |
| `enterprise_id` | `string` | Yes | Enterprise ID |
| `questions` | `string` | No | Questions separated by pipe (`\|`) |
| `is_swift` | `boolean` | No | Swift mode enabled |

**Example:**

```json
[
  {
    "user_id": "user_id",
    "enterprise_id": "e_id",
    "questions": "How many ROs did we close in May 2023?| How many appointments are there today?",
    "is_swift": true
  }
]
```

### 200 — Success

Returns a plain-English response string.

```json
{
  "result": "In May 2023, you closed 50 ROs."
}
```

---

## Error Responses

All endpoints share the same error response format:

```json
{
  "code": <int>,
  "message": "<string>"
}
```

| Status | Description | Extra Headers |
|--------|-------------|---------------|
| **400** | Bad Request | `Request-Id` |
| **401** | Unauthorized | `Request-Id` |
| **403** | Forbidden | — |
| **429** | Too Many Requests | `Retry-After` (seconds) |
| **500** | Internal Server Error | `Request-Id` |
| **502** | Bad Gateway | — |
| **503** | Service Unavailable | `Request-Id` |
| **504** | Gateway Timeout | — |
