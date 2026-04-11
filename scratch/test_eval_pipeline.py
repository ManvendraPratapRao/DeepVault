import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from scripts.eval_engine_metrics import EvalEngine

async def test_lite():
    engine = EvalEngine()
    # Mocking or limiting for a quick check
    engine.strategies = ["fixed"] # Only one
    
    print("🚀 Starting Lite Smoke Test...")
    await engine.initialize()
    
    questions = engine._load_questions()
    if not questions:
        print("❌ No questions found!")
        return
        
    sample = [questions[0]] # Just one question
    
    print(f"DEBUG: Selected Q: {sample[0]['question']}")
    
    # Manually run the core logic for one item
    try:
        strategy = "fixed"
        item = sample[0]
        
        from app.core.models.query import QueryRequest
        req = QueryRequest(query_text=item["question"], strategy=strategy, top_k=3)
        resp = await engine.query_service.ask(req)
        
        context = "\n\n".join([c.content for c in resp.sources])
        
        print("⚖️ Judging...")
        eval_metrics = await engine._evaluate_answer(
            item["question"], resp.answer, context, item["answer"]
        )
        
        print(f"✅ Success! Metrics: {eval_metrics}")
        print(f"Latency: {resp.latency_ms:.1f}ms")
        
    except Exception as e:
        print(f"❌ Error during lite test: {e}")

if __name__ == "__main__":
    asyncio.run(test_lite())
