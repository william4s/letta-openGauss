#!/usr/bin/env python3
"""
测试 OpenGauss 数据库初始化功能
这个脚本测试项目启动时的 OpenGauss 数据库初始化功能
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
dotenv_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

# Add the letta directory to the Python path
letta_dir = Path(__file__).parent.parent
sys.path.insert(0, str(letta_dir))

def test_opengauss_initialization():
    """测试 OpenGauss 数据库初始化"""
    
    # 首先设置必要的环境变量来启用 OpenGauss
    os.environ['ENABLE_OPENGAUSS'] = 'true'
    os.environ['PG_URI'] = f"postgresql://{os.getenv('OPENGAUSS_USERNAME', 'opengauss')}:{os.getenv('OPENGAUSS_PASSWORD', '0pen_gauss')}@{os.getenv('OPENGAUSS_HOST', 'localhost')}:{os.getenv('OPENGAUSS_PORT', '5432')}/{os.getenv('OPENGAUSS_DATABASE', 'letta')}"
    
    print("=== 测试 OpenGauss 数据库初始化功能 ===")
    print(f"ENABLE_OPENGAUSS: {os.getenv('ENABLE_OPENGAUSS')}")
    print(f"PG_URI: {os.getenv('PG_URI')}")
    
    try:
        # 重新加载 settings 模块以应用新的环境变量
        import importlib
        from letta import settings as settings_module
        importlib.reload(settings_module)
        
        # 导入相关模块
        from letta.server.db import DatabaseRegistry
        from letta.settings import settings
        from sqlalchemy import text
        
        # 创建新的数据库注册表实例来测试
        test_registry = DatabaseRegistry()
        
        print(f"OpenGauss 配置:")
        print(f"  - enable_opengauss: {settings.enable_opengauss}")
        print(f"  - opengauss_host: {settings.opengauss_host}")
        print(f"  - opengauss_port: {settings.opengauss_port}")
        print(f"  - opengauss_database: {settings.opengauss_database}")
        print(f"  - opengauss_username: {settings.opengauss_username}")
        print(f"  - opengauss_table_name: {settings.opengauss_table_name}")
        print(f"  - letta_pg_uri_no_default: {settings.letta_pg_uri_no_default}")
        print()
        
        # 测试同步数据库初始化
        print("测试同步数据库初始化...")
        test_registry.initialize_sync(force=True)
        print("✓ 同步数据库初始化成功")
        
        # 测试异步数据库初始化
        print("测试异步数据库初始化...")
        test_registry.initialize_async(force=True)
        print("✓ 异步数据库初始化成功")
        
        # 测试数据库连接
        print("测试数据库连接...")
        with test_registry.session() as session:
            # 执行一个简单的查询来测试连接
            result = session.execute(text("SELECT 1 as test")).fetchone()
            print(f"✓ 数据库连接测试成功，结果: {result}")
        
        print()
        print("=== 所有测试通过！===")
        return True
        
    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_without_opengauss():
    """测试不启用 OpenGauss 时的正常行为"""
    print("\n=== 测试未启用 OpenGauss 时的行为 ===")
    
    # 临时禁用 OpenGauss
    original_enable = os.environ.get('ENABLE_OPENGAUSS')
    original_pg_uri = os.environ.get('LETTA_PG_URI')
    
    try:
        os.environ['ENABLE_OPENGAUSS'] = 'false'
        if 'LETTA_PG_URI' in os.environ:
            del os.environ['LETTA_PG_URI']
        
        # 重新加载 settings 模块
        import importlib
        from letta import settings as settings_module
        importlib.reload(settings_module)
        
        from letta.server.db import DatabaseRegistry
        
        # 创建新的数据库注册表实例
        test_registry = DatabaseRegistry()
        
        print("测试 SQLite 初始化（OpenGauss 未启用）...")
        test_registry.initialize_sync(force=True)
        print("✓ SQLite 初始化成功")
        
        return True
        
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False
        
    finally:
        # 恢复原始环境变量
        if original_enable:
            os.environ['ENABLE_OPENGAUSS'] = original_enable
        if original_pg_uri:
            os.environ['LETTA_PG_URI'] = original_pg_uri

if __name__ == "__main__":
    success = True
    
    # 测试 OpenGauss 初始化
    success &= test_opengauss_initialization()
    
    # 测试不启用 OpenGauss 的情况
    success &= test_without_opengauss()
    
    if success:
        print("\n🎉 所有测试都通过了！")
        sys.exit(0)
    else:
        print("\n❌ 有测试失败")
        sys.exit(1)
