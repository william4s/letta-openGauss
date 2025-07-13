#!/usr/bin/env python3
"""
检查 Letta 设置配置
"""

import os
import sys
from pathlib import Path

# Add the letta directory to the Python path
letta_dir = Path(__file__).parent.parent
sys.path.insert(0, str(letta_dir))

def check_settings():
    """检查当前的 Letta 设置"""
    print("=== Letta 设置检查 ===")
    
    try:
        from letta.settings import settings
        
        print(f"✓ Settings 模块加载成功")
        print()
        
        print("📊 数据库设置:")
        print(f"  - enable_opengauss: {settings.enable_opengauss}")
        print(f"  - pg_uri: {settings.pg_uri}")
        print(f"  - letta_pg_uri: {settings.letta_pg_uri}")
        print(f"  - letta_pg_uri_no_default: {settings.letta_pg_uri_no_default}")
        print()
        
        print("🔧 OpenGauss 特定设置:")
        print(f"  - opengauss_host: {settings.opengauss_host}")
        print(f"  - opengauss_port: {settings.opengauss_port}")
        print(f"  - opengauss_database: {settings.opengauss_database}")
        print(f"  - opengauss_username: {settings.opengauss_username}")
        print(f"  - opengauss_password: {'***' if settings.opengauss_password else None}")
        print(f"  - opengauss_table_name: {settings.opengauss_table_name}")
        print(f"  - opengauss_ssl_mode: {settings.opengauss_ssl_mode}")
        print()
        
        print("🌍 相关环境变量:")
        env_vars = [
            'LETTA_ENABLE_OPENGAUSS',
            'LETTA_PG_URI',
            'LETTA_OPENGAUSS_HOST',
            'LETTA_OPENGAUSS_PORT',
            'LETTA_OPENGAUSS_DATABASE',
            'LETTA_OPENGAUSS_USERNAME',
            'LETTA_OPENGAUSS_PASSWORD',
            'LETTA_OPENGAUSS_TABLE_NAME',
            'LETTA_OPENGAUSS_SSL_MODE'
        ]
        
        for var in env_vars:
            value = os.getenv(var)
            if var.endswith('PASSWORD') and value:
                value = '***'
            print(f"  - {var}: {value}")
        
        print()
        
        # 检测将使用的数据库类型
        if settings.letta_pg_uri_no_default:
            if settings.enable_opengauss:
                print("🎯 预期行为: 将使用 OpenGauss 数据库（带初始化）")
            else:
                print("🎯 预期行为: 将使用 PostgreSQL 数据库（无 OpenGauss 初始化）")
        else:
            print("🎯 预期行为: 将使用 SQLite 数据库")
        
        print()
        
        return True
        
    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    check_settings()
