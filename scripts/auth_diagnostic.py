import os
import sys
from pathlib import Path

# Add root to sys.path
sys.path.append(str(Path.cwd()))

try:
    from app.config import settings
    k = settings.GROQ_API_KEY
    
    print("--- DEEPVAULT AUTH DIAGNOSTIC ---")
    print(f"Key Length: {len(k)}")
    print(f"Key Prefix: {k[:7]}...")
    print(f"Key Suffix: ...{k[-4:]}")
    
    # Check for common pitfalls
    if k.startswith('"') or k.endswith('"'):
        print("ALERT: Key contains literal quotes!")
    if k.isspace():
        print("ALERT: Key is only whitespace!")
    if len(k) < 10:
        print("ALERT: Key is suspiciously short!")
        
    print("--- SOURCE ANALYSIS ---")
    # Check if a shell variable exists
    shell_val = os.environ.get("GROQ_API_KEY")
    if shell_val:
        print(f"Shell Override Detected: YES (Length {len(shell_val)})")
    else:
        print("Shell Override Detected: NO")
        
except Exception as e:
    print(f"DIAGNOSTIC FAILED: {e}")
