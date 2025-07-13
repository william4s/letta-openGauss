#!/usr/bin/env python3
"""
JR.PDF RAG系统配置检查脚本
确保所有必要的配置都正确设置
"""

import os
import sys
from pathlib import Path

# 添加 letta 模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))


def check_environment():
    """检查环境配置"""
    print("🔍 检查JR.PDF RAG系统环境...")
    print("=" * 50)
    
    checks = []
    
    # 1. 检查PDF文件
    jr_pdf_path = current_dir / "jr.pdf"
    if jr_pdf_path.exists():
        file_size = jr_pdf_path.stat().st_size
        print(f"✅ JR.PDF文件存在: {jr_pdf_path}")
        print(f"   文件大小: {file_size / 1024:.1f} KB")
        checks.append(True)
    else:
        print(f"❌ JR.PDF文件不存在: {jr_pdf_path}")
        checks.append(False)
    
    # 2. 检查Letta模块
    try:
        from letta_client import Letta
        print("✅ letta_client 模块可用")
        checks.append(True)
    except ImportError as e:
        print(f"❌ letta_client 模块不可用: {e}")
        checks.append(False)
    
    # 3. 检查OpenGauss配置
    required_env_vars = [
        'OPENGAUSS_HOST',
        'OPENGAUSS_PORT', 
        'OPENGAUSS_DATABASE',
        'OPENGAUSS_USERNAME'
    ]
    
    opengauss_configured = True
    for var in required_env_vars:
        if os.getenv(var):
            print(f"✅ {var}: {os.getenv(var)}")
        else:
            print(f"⚠️ {var}: 未设置")
            opengauss_configured = False
    
    if opengauss_configured:
        print("✅ OpenGauss环境变量配置完整")
    else:
        print("⚠️ OpenGauss环境变量配置不完整")
    
    checks.append(opengauss_configured)
    
    # 4. 检查Letta服务器连接
    try:
        client = Letta(base_url="http://localhost:8283")
        # 尝试获取源列表来测试连接
        sources = client.sources.list()
        print("✅ Letta服务器连接正常")
        print(f"   现有文档源数量: {len(sources)}")
        checks.append(True)
    except Exception as e:
        print(f"❌ Letta服务器连接失败: {e}")
        checks.append(False)
    
    # 5. 检查模型可用性
    print("\n🧠 检查指定模型:")
    print("• LLM模型: openai/qwen3")
    print("• 嵌入模型: bge/bge-m3")
    
    # 总结
    print("\n" + "=" * 50)
    if all(checks):
        print("✅ 所有检查通过，系统可以正常运行!")
        return True
    else:
        print("❌ 部分检查失败，请解决上述问题")
        return False


def setup_instructions():
    """显示设置说明"""
    print("\n📋 JR.PDF RAG系统设置说明:")
    print("=" * 50)
    
    print("\n1. 确保PDF文件存在:")
    print(f"   {current_dir / 'jr.pdf'}")
    
    print("\n2. 启动Letta服务器:")
    print("   cd /path/to/letta")
    print("   python -m letta server")
    
    print("\n3. 配置OpenGauss环境变量:")
    print("   export OPENGAUSS_HOST=localhost")
    print("   export OPENGAUSS_PORT=5432")
    print("   export OPENGAUSS_DATABASE=letta")
    print("   export OPENGAUSS_USERNAME=postgres")
    print("   export OPENGAUSS_PASSWORD=your_password")
    
    print("\n4. 运行RAG系统:")
    print("   python jr_rag_system.py")
    print("   或")
    print("   python quick_jr_test.py")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--setup":
        setup_instructions()
    else:
        success = check_environment()
        if not success:
            print("\n运行 'python jr_config_check.py --setup' 查看设置说明")
