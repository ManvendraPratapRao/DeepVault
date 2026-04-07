# Project Aurora API Documentation
=====================================

### Service: Predictive Analytics Engine

The Predictive Analytics Engine (PAE) service within Project Aurora is responsible for generating predictive models for customer churn analysis. This service is a critical component of our overall product offering and is used extensively throughout the platform.

**Base URL**
------------

`https://aurora-svc.omnisynapse.com/pa/api`

**Authentication**
-----------------

* Authentication method: JSON Web Token (JWT)
* Token format: `Bearer <token>`
* Token acquisition: Obtain a token by sending a `POST` request to `/login` with valid credentials

### Endpoints

#### GET /models

* Retrieve a list of available predictive models
* **Request Example**
```json
{
  "models": ["churn_v1", "churn_v2"]
}
```
* **Response Example**
```json
{
  "models": ["churn_v1", "churn_v2"]
}
```

#### POST /models/churn_v1/predict

* Predict customer churn using the `churn_v1` model
* **Request Example**
```json
{
  "customer_id": 12345,
  "features": {
    "age": 30,
    "income": 50000
  }
}
```
* **Response Example**
```json
{
  "churn_probability": 0.2
}
```

**Error Codes**
---------------

* `401 Unauthorized`: Invalid token or token expiration
* `404 Not Found`: Invalid model or endpoint

**Connections to Project Sentinel**
----------------------------------

The Predictive Analytics Engine service was inspired by the work done on Project Sentinel, specifically the development of the `sentinel_model` by Sarah (ML Engineer). This service builds upon the concepts and techniques explored in Project Sentinel to provide a robust and scalable predictive analytics engine.

**Contributors**
----------------

* Rachel (Data Engineer)
* Jamal (Software Engineer)
* Chloe (ML Engineer)
* David (ML Engineer)
* Sarah (ML Engineer) - consultant and reviewer