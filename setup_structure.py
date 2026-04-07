import os
from pathlib import Path

def create_deepvault_structure():
    """
    Generates the production-grade directory structure for Project DeepVault.
    This follows the 'Clean Architecture' pattern where abstractions 
    are separated from implementations.
    """
    
    # Define the deepvault core folder (assumes we are inside the 'deepvault/' root)
    base = Path(".")
    
    structure = [
        "app/api/v1/routes",    # FastAPI endpoints
        "app/api/schemas",      # Pydantic request/response models
        "app/core/interfaces",  # Abstract Base Classes (ABCs)
        "app/core/models",      # Domain models (Document, Chunk, etc.)
        "app/infrastructure/chunkers",
        "app/infrastructure/retrievers",
        "app/infrastructure/llm",
        "app/infrastructure/stores",
        "app/services",         # Orchestration logic (IngestionService, QueryService)
        "app/prompts/v1",       # Versioned prompt templates
        "tests/unit",           # Independent component tests
        "tests/integration",    # End-to-end pipeline tests
        "docker",               # Dockerfiles and compose
        "docs/adrs",            # Architecture Decision Records
        "scripts",              # Migration or data loading scripts
    ]

    for folder in structure:
        (base / folder).mkdir(parents=True, exist_ok=True)
        # Create an __init__.py in every python directory to make them packages
        if "app" in folder or "tests" in folder:
            init_file = base / folder / "__init__.py"
            init_file.touch(exist_ok=True)
            
    # Create the top-level app files
    (base / "app" / "__init__.py").touch(exist_ok=True)
    (base / "app" / "main.py").touch(exist_ok=True)
    (base / "app" / "config.py").touch(exist_ok=True)
    (base / "app" / "dependencies.py").touch(exist_ok=True)
    
    # Create empty .env and .gitignore
    (base / ".env").touch(exist_ok=True)
    (base / ".gitignore").write_text("__pycache__/\n.venv/\n.env\n*.pyc\n.pytest_cache/\n")

    print("✅ DeepVault Production Structure Created Successfully!")

if __name__ == "__main__":
    create_deepvault_structure()
