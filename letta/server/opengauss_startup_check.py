"""
OpenGauss启动兼容性检查
在服务器启动时执行兼容性检查和自动修复
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from letta.settings import settings

logger = logging.getLogger(__name__)

async def check_and_fix_compatibility():
    """检查并修复OpenGauss兼容性问题"""
    if not settings.enable_opengauss:
        return True
        
    try:
        # 创建连接测试
        pg_uri = settings.letta_pg_uri
        if pg_uri.startswith("postgresql://"):
            async_pg_uri = pg_uri.replace("postgresql://", "postgresql+asyncpg://")
        else:
            async_pg_uri = f"postgresql+asyncpg://{pg_uri.split('://', 1)[1]}"
        
        async_pg_uri = async_pg_uri.replace("sslmode=", "ssl=")
        
        engine = create_async_engine(async_pg_uri, echo=False)
        
        async with engine.begin() as conn:
            # 检查vector类型使用情况
            result = await conn.execute(text("""
                SELECT COUNT(*) 
                FROM pg_attribute 
                JOIN pg_class ON pg_attribute.attrelid = pg_class.oid
                JOIN pg_namespace ON pg_class.relnamespace = pg_namespace.oid
                JOIN pg_type ON pg_attribute.atttypid = pg_type.oid
                WHERE typname = 'vector'
                  AND NOT attisdropped
                  AND attnum > 0
                  AND schemaname = 'public'
            """))
            
            vector_count = result.scalar()
            
            if vector_count > 0:
                logger.warning(f"⚠️ 发现 {vector_count} 个vector类型列，可能导致兼容性问题")
                logger.warning("建议运行: python migrate_to_opengauss_compatibility.py")
                return False
            else:
                logger.info("✅ OpenGauss兼容性检查通过")
                return True
                
    except Exception as e:
        logger.error(f"❌ OpenGauss兼容性检查失败: {e}")
        return False

def run_compatibility_check():
    """同步运行兼容性检查"""
    try:
        return asyncio.run(check_and_fix_compatibility())
    except Exception as e:
        logger.error(f"❌ 兼容性检查执行失败: {e}")
        return False
