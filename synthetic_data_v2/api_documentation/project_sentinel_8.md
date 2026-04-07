**Project Sentinel: Anomaly Detection Service API Documentation**
===========================================================

**Author:** Jin (ML Engineer)
**Date:** 2023-08-25

**Connection to Project Titan:**
This service is an extension of the anomaly detection system developed for Project Titan. Emily, Principal ML Engineer, previously worked on a related issue, providing valuable insights and expertise that guided the development of this service.

**Base URL:**
https://api.omnisynapse.com/projects/sentinel/anomaly

**Authentication:**
* API Key: `x-api-key` header with a valid key (obtained from the OmniSynapse dashboard)
* OAuth 2.0: `Authorization` header with a valid access token (scopes: `projects:read`, `projects:write`)

**Endpoints:**

### GET /anomaly/types

* Retrieves a list of supported anomaly types
* Response:
```json
[
  {"id": 1, "name": "Network Anomaly"},
  {"id": 2, "name": "System Anomaly"}
]
```

### POST /anomaly/detection

* Submits a detection request for a given system or network
* Request:
```json
{
  "system_id": 123,
  "anomaly_type_id": 1,
  "threshold": 0.8
}
```
* Response:
```json
{
  "id": 456,
  "status": "PENDING",
  "result": null
}
```

### GET /anomaly/detection/{id}

* Retrieves the status and result of a detection request
* Response:
```json
{
  "id": 456,
  "status": "COMPLETED",
  "result": {
    "score": 0.9,
    "details": ["System resource usage exceeded threshold"]
  }
}
```

**Error Codes:**

* 401 Unauthorized
* 403 Forbidden
* 422 Unprocessable Entity (Invalid request data)
* 500 Internal Server Error