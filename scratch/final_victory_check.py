import httpx
import time

def test_query():
    print("--- DEEPVAULT FINAL VERIFICATION ---")
    url = "http://localhost:8000/api/v1/query"
    payload = {
        "query_text": "What is deepvault?",
        "strategy": "fixed"
    }
    headers = {
        "X-API-KEY": "deepvault_secret_key"
    }
    
    try:
        # Give API a moment to warm up
        time.sleep(10)
        
        print(f"Sending request to {url}...")
        r = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        
        print(f"HTTP Status: {r.status_code}")
        if r.status_code == 200:
            answer = r.json().get("answer", "No answer found")
            print("AUTHENTICATION: SUCCESS")
            print(f"ANSWER (truncated): {answer[:300]}...")
            print("--- STABILIZATION COMPLETE ---")
        else:
            print(f"ERROR: {r.text}")
            
    except Exception as e:
        print(f"CONNECTION FAILED: {e}")

if __name__ == "__main__":
    test_query()
