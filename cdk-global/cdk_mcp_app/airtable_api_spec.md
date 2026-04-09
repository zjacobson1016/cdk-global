# Airtable API — CDK Demo Base

**Base URL (via UC Connections Proxy):**
```
{workspace_host}/api/2.0/unity-catalog/connections/airtable-api1/proxy
```

**Base ID:** `applcG2bhZtWuEugA`

---

## Authentication

All requests are authenticated automatically via the UC connection proxy. Pass your Databricks auth headers:

```
Authorization: Bearer <databricks_token>
Content-Type: application/json
```

---

## Tables

| Table | ID | Fields |
|---|---|---|
| Customers | `tblpgNTCERtrbfLMC` | Name, Email, Phone, Status, Notes |
| Vehicles | `tblyBLM40zhrVhm9o` | Make, Model, Year, VIN, Status |
| Service Orders | `tbl8NZEF6snU6WcmP` | Order Number, Description, Priority, Status, Cost |

---

## Endpoints

### Meta

#### `GET meta/bases`
List all accessible bases.

**Response:**
```json
{
  "bases": [
    { "id": "applcG2bhZtWuEugA", "name": "CDK Demo", "permissionLevel": "create" }
  ]
}
```

#### `GET meta/bases/{baseId}/tables`
List all tables and fields in a base.

**Response:**
```json
{
  "tables": [
    {
      "id": "tblpgNTCERtrbfLMC",
      "name": "Customers",
      "fields": [
        { "name": "Name", "type": "singleLineText" },
        { "name": "Email", "type": "email" }
      ]
    }
  ]
}
```

---

### Customers (`tblpgNTCERtrbfLMC`)

#### `GET applcG2bhZtWuEugA/Customers`
List customer records.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `maxRecords` | integer | Max records to return |
| `pageSize` | integer | Records per page (max 100) |
| `offset` | string | Pagination cursor from previous response |
| `sort[0][field]` | string | Field name to sort by |
| `sort[0][direction]` | string | `asc` or `desc` |
| `filterByFormula` | string | Airtable formula to filter records |
| `fields[]` | string | Specific fields to return (repeat for multiple) |

**Response:**
```json
{
  "records": [
    {
      "id": "recXXXXXXXXXXXXXX",
      "createdTime": "2026-04-01T12:00:00.000Z",
      "fields": {
        "Name": "John Doe",
        "Email": "john@example.com",
        "Phone": "555-0100",
        "Status": "Active",
        "Notes": "VIP customer"
      }
    }
  ],
  "offset": "itr..."
}
```

#### `POST applcG2bhZtWuEugA/Customers`
Create one or more customer records.

**Request Body:**
```json
{
  "records": [
    {
      "fields": {
        "Name": "Jane Smith",
        "Email": "jane@example.com",
        "Phone": "555-0200",
        "Status": "Active",
        "Notes": "New customer"
      }
    }
  ]
}
```

**Response:** Returns created records with `id` and `createdTime`.

#### `PATCH applcG2bhZtWuEugA/Customers`
Update existing customer records.

**Request Body:**
```json
{
  "records": [
    {
      "id": "recXXXXXXXXXXXXXX",
      "fields": {
        "Status": "Inactive",
        "Notes": "Moved out of area"
      }
    }
  ]
}
```

**Response:** Returns updated records.

#### `DELETE applcG2bhZtWuEugA/Customers?records[]={recordId}`
Delete customer records.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `records[]` | string | Record ID to delete (repeat for multiple, max 10) |

**Response:**
```json
{
  "records": [
    { "id": "recXXXXXXXXXXXXXX", "deleted": true }
  ]
}
```

---

### Vehicles (`tblyBLM40zhrVhm9o`)

#### `GET applcG2bhZtWuEugA/Vehicles`
List vehicle records.

**Query Parameters:** Same as Customers.

**Response:**
```json
{
  "records": [
    {
      "id": "recXXXXXXXXXXXXXX",
      "createdTime": "2026-04-01T12:00:00.000Z",
      "fields": {
        "Make": "Toyota",
        "Model": "Camry",
        "Year": 2024,
        "VIN": "1HGBH41JXMN109186",
        "Status": "In Service"
      }
    }
  ]
}
```

#### `POST applcG2bhZtWuEugA/Vehicles`
Create vehicle records.

**Request Body:**
```json
{
  "records": [
    {
      "fields": {
        "Make": "Honda",
        "Model": "Civic",
        "Year": 2025,
        "VIN": "2HGFC2F59MH512345",
        "Status": "Available"
      }
    }
  ]
}
```

#### `PATCH applcG2bhZtWuEugA/Vehicles`
Update vehicle records. Same format as Customers PATCH.

#### `DELETE applcG2bhZtWuEugA/Vehicles?records[]={recordId}`
Delete vehicle records. Same format as Customers DELETE.

---

### Service Orders (`tbl8NZEF6snU6WcmP`)

#### `GET applcG2bhZtWuEugA/Service%20Orders`
List service order records.

**Query Parameters:** Same as Customers.

**Response:**
```json
{
  "records": [
    {
      "id": "recXXXXXXXXXXXXXX",
      "createdTime": "2026-04-01T12:00:00.000Z",
      "fields": {
        "Order Number": "SO-001",
        "Description": "Oil change and tire rotation",
        "Priority": "Medium",
        "Status": "Open",
        "Cost": 89.99
      }
    }
  ]
}
```

#### `POST applcG2bhZtWuEugA/Service%20Orders`
Create service order records.

**Request Body:**
```json
{
  "records": [
    {
      "fields": {
        "Order Number": "SO-002",
        "Description": "Brake pad replacement",
        "Priority": "High",
        "Status": "Open",
        "Cost": 350.00
      }
    }
  ]
}
```

#### `PATCH applcG2bhZtWuEugA/Service%20Orders`
Update service order records. Same format as Customers PATCH.

#### `DELETE applcG2bhZtWuEugA/Service%20Orders?records[]={recordId}`
Delete service order records. Same format as Customers DELETE.

---

## Field Types Reference

| Field | Type | Description |
|---|---|---|
| Name, Make, Model, VIN, Order Number | `singleLineText` | Plain text |
| Email | `email` | Email address |
| Phone | `phoneNumber` | Phone number |
| Notes, Description | `multilineText` | Multi-line text |
| Status, Priority | `singleSelect` | Single select dropdown |
| Year | `number` | Integer |
| Cost | `currency` | Currency value |

---

## Proxy Usage Example

```python
import requests
from databricks.sdk import WorkspaceClient

w = WorkspaceClient(profile="group-demo")
BASE = f"{w.config.host}/api/2.0/unity-catalog/connections/airtable-api1/proxy"

# List customers
resp = requests.get(
    f"{BASE}/applcG2bhZtWuEugA/Customers",
    headers={**w.config.authenticate(), "Accept-Encoding": "identity"},
)
print(resp.json())

# Create a customer
resp = requests.post(
    f"{BASE}/applcG2bhZtWuEugA/Customers",
    headers={**w.config.authenticate(), "Content-Type": "application/json"},
    json={
        "records": [{"fields": {"Name": "Test User", "Email": "test@example.com", "Status": "Active"}}]
    },
)
print(resp.json())
```
