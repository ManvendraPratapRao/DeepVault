import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"🚀 Starting DeepVault Enterprise RAG v{settings.VERSION}...")
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True, 
        log_level="info"
    )
