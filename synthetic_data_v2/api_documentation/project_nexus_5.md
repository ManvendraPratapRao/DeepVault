**Project Nexus - Model Inference Service API Documentation**
===========================================================

**Author:** Sarah (ML Engineer)
**Date:** August 8, 2023
**Base URL:** `https://api.omnisynapse.com/project-nexus`

**Authentication**
---------------

The Model Inference Service API uses JSON Web Tokens (JWT) for authentication. To obtain a JWT token, send a `POST` request to the `/login` endpoint with a JSON payload containing the username and password.

### Login Endpoint

*   **Method:** `POST`
*   **Endpoint:** `/login`
*   **Request Body:**

```json
{
    "username": "string",
    "password": "string"
}
```

*   **Response:**

```json
{
    "token": "string",
    "expires_at": "integer"
}
```

*   **Error Codes:**
    +   `401`: Invalid credentials
    +   `500`: Server error

**Endpoints**
------------

### Model List

*   **Method:** `GET`
*   **Endpoint:** `/models`
*   **Request Headers:**
    +   `Authorization: Bearer <token>`
*   **Response:**

```json
[
    {
        "id": "string",
        "name": "string",
        "description": "string",
        "created_at": "integer"
    }
]
```

*   **Error Codes:**
    +   `401`: Unauthorized
    +   `500`: Server error

### Model Details

*   **Method:** `GET`
*   **Endpoint:** `/models/{model_id}`
*   **Request Headers:**
    +   `Authorization: Bearer <token>`
*   **URL Parameters:**
    +   `model_id`: Model ID (required)
*   **Response:**

```json
{
    "id": "string",
    "name": "string",
    "description": "string",
    "created_at": "integer",
    "updated_at": "integer"
}
```

*   **Error Codes:**
    +   `401`: Unauthorized
    +   `404`: Model not found
    +   `500`: Server error

### Model Inference

*   **Method:** `POST`
*   **Endpoint:** `/models/{model_id}/infer`
*   **Request Headers:**
    +   `Authorization: Bearer <token>`
*   **URL Parameters:**
    +   `model_id`: Model ID (required)
*   **Request Body:**

```json
{
    "input_data": {
        "key1": "value1",
        "key2": "value2"
    }
}
```

*   **Response:**

```json
{
    "output_data": {
        "key1": "value1",
        "key2": "value2"
    },
    "status": "string"
}
```

*   **Error Codes:**
    +   `401`: Unauthorized
    +   `404`: Model not found
    +   `500`: Server error

### Model Update

*   **Method:** `PUT`
*   **Endpoint:** `/models/{model_id}`
*   **Request Headers:**
    +   `Authorization: Bearer <token>`
*   **URL Parameters:**
    +   `model_id`: Model ID (required)
*   **Request Body:**

```json
{
    "name": "string",
    "description": "string"
}
```

*   **Response:**

```json
{
    "id": "string",
    "name": "string",
    "description": "string",
    "created_at": "integer",
    "updated_at": "integer"
}
```

*   **Error Codes:**
    +   `401`: Unauthorized
    +   `404`: Model not found
    +   `500`: Server error

### Model Delete

*   **Method:** `DELETE`
*   **Endpoint:** `/models/{model_id}`
*   **Request Headers:**
    +   `Authorization: Bearer <token>`
*   **URL Parameters:**
    +   `model_id`: Model ID (required)
*   **Response:** `204 No Content`

*   **Error Codes:**
    +   `401`: Unauthorized
    +   `404`: Model not found
    +   `500`: Server error

**Request and Response JSON Examples**
------------------------------------

### Model List Request

```bash
curl -X GET \
  https://api.omnisynapse.com/project-nexus/models \
  -H 'Authorization: Bearer <token>'
```

### Model Details Request

```bash
curl -X GET \
  https://api.omnisynapse.com/project-nexus/models/<model_id> \
  -H 'Authorization: Bearer <token>'
```

### Model Inference Request

```bash
curl -X POST \
  https://api.omnisynapse.com/project-nexus/models/<model_id>/infer \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"input_data": {"key1": "value1", "key2": "value2"}}'
```

### Model Update Request

```bash
curl -X PUT \
  https://api.omnisynapse.com/project-nexus/models/<model_id> \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"name": "new_name", "description": "new_description"}'
```

### Model Delete Request

```bash
curl -X DELETE \
  https://api.omnisynapse.com/project-nexus/models/<model_id> \
  -H 'Authorization: Bearer <token>'
```

**Error Handling**
-------------------

The Model Inference Service API uses the following error codes to indicate the type of error that occurred.

*   `401`: Unauthorized - The user is not authenticated or authorized to perform the requested action.
*   `404`: Not Found - The requested resource (model, endpoint, etc.) was not found.
*   `500`: Internal Server Error - An unexpected error occurred on the server.

By following this API documentation, you should be able to use the Model Inference Service API to create, update, delete, and infer models. If you encounter any issues or have questions, please don't hesitate to reach out to the OmniSynapse support team.