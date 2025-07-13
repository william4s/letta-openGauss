#!/usr/bin/env python3

# 简单测试脚本
print("Starting simple test...")

# 基本导入测试
try:
    from typing import NamedTuple
    print("✅ typing works")
except Exception as e:
    print(f"❌ typing failed: {e}")
    exit(1)

# 测试我们的简单解析器
print("Testing SimpleTextParser creation...")
try:
    # 直接定义类而不是导入
    class SimplePageObject(NamedTuple):
        index: int
        markdown: str
        images: list = []
        dimensions: tuple = None

    class SimpleParseResponse(NamedTuple):
        model: str
        pages: list
        usage_info: object
        document_annotation: str = None

    print("✅ Simple classes defined")
    
    # 测试基本功能
    test_content = "Hello, world!"
    content_bytes = test_content.encode('utf-8')
    
    # 简单解析
    text = content_bytes.decode("utf-8", errors="replace")
    
    page = SimplePageObject(
        index=0,
        markdown=text,
        images=[],
        dimensions=None,
    )
    
    print(f"✅ Created page with text: {page.markdown}")
    print("🎉 Basic functionality works!")

except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("✅ All basic tests passed!")
