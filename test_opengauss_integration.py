#!/usr/bin/env python3
"""
Test script to verify OpenGauss integration with Letta
"""

import os
import sys
from letta.settings import settings
from letta.server.db import DatabaseRegistry

def test_opengauss_connection():
    """Test OpenGauss database connection and configuration"""
    print("🔍 Testing OpenGauss Integration with Letta")
    print("=" * 50)
    
    # Test 1: Verify settings are loaded correctly
    print("📋 Test 1: Checking settings configuration...")
    print(f"   - LETTA_PG_URI configured: {bool(settings.letta_pg_uri_no_default)}")
    if settings.letta_pg_uri_no_default:
        # Hide password for security
        uri_safe = settings.letta_pg_uri.replace(':0pen_gauss@', ':***@')
        print(f"   - Database URI: {uri_safe}")
    
    # Test 2: Test database connection
    print("\n🔌 Test 2: Testing database connection...")
    try:
        db_registry = DatabaseRegistry()
        db_registry.initialize_sync()
        print("   ✓ Database connection successful")
        
        # Test 3: Verify table creation
        print("\n📊 Test 3: Checking database tables...")
        from sqlalchemy import text
        engine = db_registry.get_engine()
        
        with engine.connect() as connection:
            # Check if key tables exist
            result = connection.execute(text("""
                SELECT COUNT(*) as table_count 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """))
            table_count = result.scalar()
            print(f"   ✓ Found {table_count} tables in database")
            
            # Check Alembic version
            result = connection.execute(text("SELECT version_num FROM alembic_version"))
            version = result.scalar()
            print(f"   ✓ Alembic version: {version}")
            
            # Test a simple query
            result = connection.execute(text("SELECT COUNT(*) FROM organizations"))
            org_count = result.scalar()
            print(f"   ✓ Organizations table accessible (count: {org_count})")
            
    except Exception as e:
        print(f"   ✗ Database test failed: {e}")
        return False
    
    print("\n🎉 All tests passed! OpenGauss integration is working correctly.")
    return True

if __name__ == "__main__":
    success = test_opengauss_connection()
    sys.exit(0 if success else 1)
