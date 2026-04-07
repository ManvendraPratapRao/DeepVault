# Project Sentinel API Documentation
## Overview
Project Sentinel's Anomaly Detection Service (ADS) provides real-time anomaly detection capabilities for high-velocity data streams. This document outlines the API specification for ADS.

### Base URL
`https://ads.sentinel.omnisynapse.com`

### Authentication
ADS uses OAuth 2.0 for authentication. Clients must obtain an access token by exchanging a client ID and secret with the authorization server.

* **Token Endpoint**: `https://auth.omnisynapse.com/token`
* **Client ID**: `ADS_CLIENT_ID`
* **Client Secret**: `ADS_CLIENT_SECRET`
* **Grant Type**: `client_credentials`

### Endpoints

#### GET /models
Retrieve a list of available models for anomaly detection.

* **Request**: `GET /models`
* **Response**: 
```json
[
  {
    "id": "MODEL_123",
    "name": "Default Model",
    "description": "Default model for anomaly detection"
  },
  {
    "id": "MODEL_456",
    "name": "Custom Model",
    "description": "Custom model for anomaly detection"
  }
]
```
* **Error Codes**:
	+ `500`: Internal Server Error
	+ `401`: Unauthorized

#### POST /anomalies
Submit a data point for anomaly detection.

* **Request**: 
```json
{
  "model_id": "MODEL_123",
  "data": {
    "feature1": 10.5,
    "feature2": 20.3
  }
}
```
* **Response**: 
```json
{
  "anomaly_score": 0.8,
  "is_anomaly": true
}
```
* **Error Codes**:
	+ `400`: Bad Request
	+ `500`: Internal Server Error