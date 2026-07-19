# Authentication Guide — JWT Role-Based Access Control

**Phase:** 4 (Production Hardening)  
**Status:** Planned — Implementation Pending (Session 21)

---

## Overview

DeepVault currently uses a static API key (`X-API-KEY` header) for authentication. Phase 4 will replace this with a proper **JWT (JSON Web Token)** authentication system with three user roles:

| Role | Permissions |
|------|------------|
| `admin` | Full access. Can ingest, query, delete documents, run evals, and manage API keys. |
| `user` | Can query the API and view their own query history. Cannot ingest or delete. |
| `viewer` | Read-only. Can view documents and query results but cannot submit new queries. |

---

## Current Authentication (Available Now)

All endpoints are protected by the `X-API-KEY` header:

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query_text": "..."}'
```

The API key is validated against `settings.API_KEY` in `app/api/middleware/limiter.py`.

To change the key: set `API_KEY=your_secure_key` in `.env`.

---

## Planned JWT Implementation (Session 21)

### 1. Token Endpoint

```http
POST /api/v1/auth/token
Content-Type: application/json

{
  "username": "analyst@company.com",
  "password": "secure_password"
}
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### 2. JWT Payload Structure

```json
{
  "sub": "user@company.com",
  "role": "user",
  "exp": 1714500000,
  "iat": 1714496400
}
```

### 3. Protected Route Example

```python
# app/api/middleware/auth.py
from jose import jwt, JWTError
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def require_role(roles: list[str]):
    async def _check(credentials = Security(security)):
        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.JWT_SECRET_KEY,
                algorithms=["HS256"]
            )
            user_role = payload.get("role")
            if user_role not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{user_role}' is not authorized for this endpoint."
                )
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token."
            )
    return _check
```

### 4. Role-Based Route Protection

```python
# Query endpoint — any authenticated user
@router.post("/query")
async def query(
    request: QueryRequest,
    _user = Depends(require_role(["admin", "user"])),
    ...
):
    ...

# Ingest endpoint — admin only
@router.post("/documents")
async def ingest(
    request: IngestRequest,
    _user = Depends(require_role(["admin"])),
    ...
):
    ...
```

### 5. Dependencies

```toml
# pyproject.toml
python-jose = {extras = ["cryptography"], version = ">=3.3"}
passlib = {extras = ["bcrypt"], version = ">=1.7"}
```

---

## Required Environment Variables (Phase 4)

```env
# JWT Configuration
JWT_SECRET_KEY=your_256_bit_random_secret_key_here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# User store (Phase 4 — stored in PostgreSQL)
# Phase 4 interim: store in a simple config or SQLite users table
```

Generate a secure secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Migration Plan

Phase 4 JWT auth will be backward-compatible during transition:

1. Static `X-API-KEY` continues to work until Phase 4 is fully deployed.
2. New JWT middleware checks `Authorization: Bearer <token>` first.
3. Falls back to `X-API-KEY` if JWT header is absent (for existing integrations).
4. Static key is deprecated after Phase 4 release.

---

## Security Considerations

- **Never commit** `JWT_SECRET_KEY` to the repository. Use `.env` or a secrets manager.
- JWT tokens expire after `JWT_EXPIRE_MINUTES`. Refresh tokens are not planned for Phase 4 (short-lived tokens are sufficient for an API use case).
- Passwords are hashed with bcrypt (via `passlib`). Never store plaintext passwords.
- The `/auth/token` endpoint is rate-limited (5 attempts/minute per IP) to prevent brute force.
- Use HTTPS in production. JWT tokens sent over HTTP are readable in transit.
