**Project Aurora API Documentation**
======================================

**Service:** Predictive Maintenance Insights
------------------------------------------

**Description:** This API provides Predictive Maintenance insights to help optimize equipment lifespan and reduce downtime. It aggregates data from various sources, including IoT sensors, maintenance records, and sensor metadata.

**Base URL:** `https://api.omnisynapse.com/project-aurora/predictive-maintenance`

**Authentication:**

*   API Key: Provide your API key in the `Authorization` header with the format `Bearer <api-key>`.
*   OAuth 2.0: Use OAuth 2.0 to authenticate with OmniSynapse. We support the `client_credentials` flow. Contact your account manager for more information.

**Endpoints:**

### **GET /equipment**

*   **Retrieve a list of equipment** with Predictive Maintenance insights.
*   **Authentication Required:** API Key or OAuth 2.0
*   **Request Parameters:**
    *   `equipment_id` (optional): Filter by equipment ID.
    *   `limit` (optional): Limit the number of results.
    *   `offset` (optional): Offset the results.
*   **Request Example:** `GET /equipment?equipment_id=123&limit=10&offset=0`
*   **Response Example:**

```json
[
  {
    "equipment_id": 123,
    "name": "Engine 1",
    "predictive_maintenance_score": 0.8,
    "recommended_maintenance_date": "2024-01-15",
    "sensor_metadata": {
      "temperature": 50,
      "vibration": 100
    }
  },
  {
    "equipment_id": 456,
    "name": "Pump 2",
    "predictive_maintenance_score": 0.9,
    "recommended_maintenance_date": "2024-02-01",
    "sensor_metadata": {
      "pressure": 200,
      "flow_rate": 500
    }
  }
]
```

### **GET /equipment/{equipment_id}/predictions**

*   **Retrieve Predictive Maintenance predictions** for a specific equipment.
*   **Authentication Required:** API Key or OAuth 2.0
*   **Request Parameters:**
    *   `equipment_id`: Required
*   **Request Example:** `GET /equipment/123/predictions`
*   **Response Example:**

```json
[
  {
    "prediction_date": "2024-01-15",
    "failure_probability": 0.2,
    "recommended_maintenance_action": "Replace bearings"
  },
  {
    "prediction_date": "2024-02-01",
    "failure_probability": 0.1,
    "recommended_maintenance_action": "Check fluid levels"
  }
]
```

### **POST /equipment/{equipment_id}/predictions**

*   **Create a new Predictive Maintenance prediction** for a specific equipment.
*   **Authentication Required:** API Key or OAuth 2.0
*   **Request Body:**
    *   `prediction_date`: Required
    *   `failure_probability`: Required
    *   `recommended_maintenance_action`: Required
*   **Request Example:**

```json
{
  "prediction_date": "2024-03-01",
  "failure_probability": 0.5,
  "recommended_maintenance_action": "Replace engine"
}
```

**Error Codes:**

*   `400 Bad Request`: Invalid request parameters or missing required fields.
*   `401 Unauthorized`: Invalid API key or OAuth 2.0 credentials.
*   `404 Not Found`: Equipment or prediction not found.
*   `500 Internal Server Error`: Server-side error or data inconsistency.

**Cross-Referencing:**

Sarah (ML Engineer) previously worked on a related issue regarding data preprocessing for Predictive Maintenance models. She reviewed this API documentation and provided valuable feedback.

**Release Notes:**

*   Initial release: 2023-12-15
*   Updated: 2024-01-01 (minor bug fixes and documentation improvements)

Please note that this API documentation is subject to change based on customer feedback and new feature development.