import asyncio
import time
import httpx
import statistics

API_URL = "http://127.0.0.1:8000"

async def run_benchmark():
    print(f"Connecting to {API_URL}...")
    
    async with httpx.AsyncClient() as client:
        try:
            health = await client.get(f"{API_URL}/api/v1/health")
            data = health.json()
            redis_status = data.get("components", {}).get("redis", "disconnected")
            print(f"DeepVault Health: {data.get('status')} | Redis: {redis_status}")
            
            if redis_status != "connected":
                print("\n[WARNING] Redis is disconnected! Caching speedups will not be observed.")
        except Exception as e:
            print(f"Failed to connect to API: {e}")
            return

        query_payload = {
            "query_text": "What is the architecture of DeepVault?",
            "top_k": 3
        }

        print("\n--- Running 10 Queries (Simulating cache warming) ---")
        latencies = []
        
        for i in range(10):
            start = time.perf_counter()
            resp = await client.post(f"{API_URL}/api/v1/query", json=query_payload)
            if resp.status_code == 200:
                data = resp.json()
                # Use server-reported latency from the payload for highest accuracy
                latencies.append(data.get("latency_ms", 0))
                print(f"Query {i+1}/10 completed in {latencies[-1]:.2f}ms")
            else:
                print(f"Query {i+1} failed with status {resp.status_code}")
                
        if latencies:
            print(f"\n--- BENCHMARK RESULTS ---")
            print(f"Initial Cold Query: {latencies[0]:.2f}ms")
            
            if len(latencies) > 1:
                cached_avg = statistics.mean(latencies[1:])
                reduction = ((latencies[0] - cached_avg) / latencies[0]) * 100
                print(f"Average Cached Query (2-10): {cached_avg:.2f}ms")
                print(f"Speedup via Redis: {reduction:.1f}% Latency Reduction")
            print("=========================")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
