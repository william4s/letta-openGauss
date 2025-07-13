#!/usr/bin/env python3

import os
import sys
from pathlib import Path

print(f"Current working directory: {os.getcwd()}")
print(f"Python executable: {sys.executable}")

# Test if .env file exists
env_file = Path(".env")
print(f".env file exists: {env_file.exists()}")
if env_file.exists():
    print(f".env file content:")
    print(env_file.read_text())

# Test environment variables directly
print(f"\nEnvironment variables:")
for var in ["LETTA_PG_URI", "LETTA_PG_DB", "LETTA_ENABLE_OPENGAUSS"]:
    print(f"{var}: {os.getenv(var)}")

# Test dotenv loading
try:
    from dotenv import load_dotenv
    load_dotenv()
    print(f"\nAfter loading .env:")
    for var in ["LETTA_PG_URI", "LETTA_PG_DB", "LETTA_ENABLE_OPENGAUSS"]:
        print(f"{var}: {os.getenv(var)}")
except ImportError:
    print("dotenv not available")

# Test letta settings
try:
    print(f"\nLoading Letta settings...")
    from letta.settings import settings
    print(f"Settings loaded successfully")
    print(f"enable_opengauss: {settings.enable_opengauss}")
    print(f"pg_uri: {repr(settings.pg_uri)}")
    print(f"pg_db: {repr(settings.pg_db)}")
    print(f"letta_pg_uri_no_default: {repr(settings.letta_pg_uri_no_default)}")
except Exception as e:
    print(f"Error loading settings: {e}")
    import traceback
    traceback.print_exc()
