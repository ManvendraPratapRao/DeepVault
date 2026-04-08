from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.middleware.logging import LoggingMiddleware

# 1. Create a tiny test app
app = FastAPI()
app.add_middleware(LoggingMiddleware)


@app.get("/test")
async def test_endpoint():
    return {"message": "logging works!"}


def run_test():
    client = TestClient(app)
    print("\n--- TRIGGERING API CALL ---\n")
    response = client.get("/test")

    # The X-Request-ID should be set by our middleware
    request_id = response.headers.get("X-Request-ID")

    print(f"CLIENT RECEIVED HEADER: X-Request-ID: {request_id}")
    print(f"CLIENT RECEIVED BODY: {response.json()}")
    print("\n--- TEST COMPLETE ---\n")


if __name__ == "__main__":
    run_test()
