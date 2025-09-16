#!/usr/bin/env python3
"""
OpenGauss数据库兼容性迁移脚本
将vector类型转换为text类型
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from letta.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_vector_columns():
    """迁移vector类型列为text类型"""
    if not settings.letta_pg_uri_no_default or not settings.enable_opengauss:
        logger.info("跳过迁移 - 不是OpenGauss环境")
        return
        
    # 创建异步连接
    pg_uri = settings.letta_pg_uri
    if pg_uri.startswith("postgresql://"):
        async_pg_uri = pg_uri.replace("postgresql://", "postgresql+asyncpg://")
    else:
        async_pg_uri = f"postgresql+asyncpg://{pg_uri.split('://', 1)[1]}"
    
    async_pg_uri = async_pg_uri.replace("sslmode=", "ssl=")
    
    try:
        engine = create_async_engine(async_pg_uri, echo=True)
        
        async with engine.begin() as conn:
            # 检查是否存在vector类型的列
            result = await conn.execute(text("""
                SELECT schemaname, tablename, attname, typname
                FROM pg_attribute 
                JOIN pg_class ON pg_attribute.attrelid = pg_class.oid
                JOIN pg_namespace ON pg_class.relnamespace = pg_namespace.oid
                JOIN pg_type ON pg_attribute.atttypid = pg_type.oid
                WHERE typname = 'vector'
                  AND NOT attisdropped
                  AND attnum > 0
                  AND schemaname = 'public'
            """))
            
            vector_columns = result.fetchall()
            
            if not vector_columns:
                logger.info("✅ 没有发现需要迁移的vector类型列")
                return
            
            for row in vector_columns:
                schema, table, column, type_name = row
                logger.info(f"🔄 迁移 {schema}.{table}.{column} ({type_name} -> text)")
                
                try:
                    # 添加临时列
                    await conn.execute(text(f'ALTER TABLE "{schema}"."{table}" ADD COLUMN "{column}_backup" TEXT'))
                    
                    # 复制数据
                    await conn.execute(text(f'UPDATE "{schema}"."{table}" SET "{column}_backup" = "{column}"::text'))
                    
                    # 删除原列
                    await conn.execute(text(f'ALTER TABLE "{schema}"."{table}" DROP COLUMN "{column}"'))
                    
                    # 重命名列
                    await conn.execute(text(f'ALTER TABLE "{schema}"."{table}" RENAME COLUMN "{column}_backup" TO "{column}"'))
                    
                    logger.info(f"✅ 成功迁移 {schema}.{table}.{column}")
                
                except Exception as e:
                    logger.error(f"❌ 迁移失败 {schema}.{table}.{column}: {e}")
                    # 尝试清理
                    try:
                        await conn.execute(text(f'ALTER TABLE "{schema}"."{table}" DROP COLUMN IF EXISTS "{column}_backup"'))
                    except:
                        pass
        
        logger.info("✅ OpenGauss兼容性迁移完成")
        
    except Exception as e:
        logger.error(f"❌ 迁移失败: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(migrate_vector_columns())
