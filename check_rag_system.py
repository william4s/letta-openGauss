#!/usr/bin/env python3
"""
RAG系统快速启动脚本
检查环境并提供使用指南
"""

import os
import sys
import subprocess
import requests
import psycopg2

def check_python_packages():
    """检查Python包"""
    package_imports = {
        'PyPDF2': 'PyPDF2',
        'numpy': 'numpy', 
        'scikit-learn': 'sklearn',
        'psycopg2': 'psycopg2',
        'requests': 'requests'
    }
    
    missing_packages = []
    for package_name, import_name in package_imports.items():
        try:
            __import__(import_name)
            print(f"✓ {package_name}")
        except ImportError:
            missing_packages.append(package_name)
            print(f"✗ {package_name} (未安装)")
    
    if missing_packages:
        print(f"\n缺少的包: {', '.join(missing_packages)}")
        print("请运行: pip install " + " ".join(missing_packages))
        return False
    
    return True

def check_embedding_service():
    """检查Embedding服务"""
    try:
        response = requests.get("http://localhost:8283/v1/models", timeout=5)
        if response.status_code == 200:
            print("✓ BGE-M3 Embedding服务正常")
            return True
        else:
            print("✗ Embedding服务响应异常")
    except Exception as e:
        print("✗ Embedding服务未启动")
        print("  启动命令: python -m letta.server.server --host 0.0.0.0 --port 8283 --backend letta")
    return False

def check_database():
    """检查数据库"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="postgres",
            user="gaussdb",
            password="Enmo@123"
        )
        conn.close()
        print("✓ OpenGauss数据库连接正常")
        return True
    except Exception as e:
        print("✗ 数据库连接失败")
        print("  启动命令: docker run --name opengauss -e GS_PASSWORD=Enmo@123 -p 5432:5432 -d enmotech/opengauss:latest")
    return False

def check_pdf_file():
    """检查PDF文件"""
    pdf_path = "letta/examples/jr.pdf"
    if os.path.exists(pdf_path):
        print(f"✓ 测试PDF文件存在: {pdf_path}")
        return True
    else:
        print(f"✗ 测试PDF文件不存在: {pdf_path}")
        return False

def main():
    print("=" * 60)
    print("RAG系统环境检查")
    print("=" * 60)
    
    all_good = True
    
    print("\n1. 检查Python包:")
    all_good &= check_python_packages()
    
    print("\n2. 检查Embedding服务:")
    all_good &= check_embedding_service()
    
    print("\n3. 检查数据库服务:")
    all_good &= check_database()
    
    print("\n4. 检查测试文件:")
    all_good &= check_pdf_file()
    
    print("\n" + "=" * 60)
    if all_good:
        print("🎉 所有检查通过！可以运行RAG系统")
        print("\n可用的脚本:")
        print("  python letta/examples/rag_demo.py           # 完整演示")
        print("  python letta/examples/direct_embedding_rag.py  # 核心实现")
        print("  python letta/examples/quick_rag_template.py    # 快速模板")
        print("\n文档:")
        print("  README_RAG.md           # 项目概述")
        print("  RAG_USAGE_GUIDE.md      # 详细使用指南")
        print("  RAG_BUILD_GUIDE.md      # 构建指南")
    else:
        print("❌ 存在问题，请按照提示解决后重试")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
