#!/usr/bin/env python3
"""
简单直接的OpenGauss vector类型修复
避免修改太多文件，专注于解决核心问题
"""
import os
import sys
import asyncio
import logging

# 直接设置环境变量来配置数据库
os.environ["LETTA_PG_URI"] = "postgresql://opengauss:Gauss@123@localhost:5432/letta"
os.environ["ENABLE_OPENGAUSS"] = "true"

# 现在导入letta模块
sys.path.insert(0, "/home/shiwc24/ospp/letta-openGauss")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def simple_vector_fix():
    """简单的vector类型修复"""
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        
        # 创建数据库连接
        async_pg_uri = "postgresql+asyncpg://opengauss:Gauss@123@localhost:5432/letta"
        engine = create_async_engine(async_pg_uri, echo=False)
        
        logger.info("🔧 开始修复vector类型...")
        
        async with engine.begin() as conn:
            # 查找所有vector类型的列
            result = await conn.execute(text("""
                SELECT 
                    n.nspname as schema_name,
                    c.relname as table_name, 
                    a.attname as column_name,
                    t.typname as type_name
                FROM pg_attribute a
                JOIN pg_class c ON a.attrelid = c.oid
                JOIN pg_namespace n ON c.relnamespace = n.oid
                JOIN pg_type t ON a.atttypid = t.oid
                WHERE t.typname = 'vector'
                  AND a.attnum > 0
                  AND NOT a.attisdropped
                  AND n.nspname = 'public'
                ORDER BY n.nspname, c.relname, a.attname;
            """))
            
            vector_columns = result.fetchall()
            
            if not vector_columns:
                logger.info("✅ 没有发现vector类型列")
                return True
            
            logger.info(f"发现 {len(vector_columns)} 个vector类型列:")
            for row in vector_columns:
                logger.info(f"  - {row[0]}.{row[1]}.{row[2]}")
            
            # 转换每个vector列为text类型
            for schema, table, column, type_name in vector_columns:
                logger.info(f"🔄 转换 {schema}.{table}.{column} (vector -> text)")
                
                try:
                    # 方法：创建新的text列，复制数据，删除原列，重命名新列
                    temp_column = f"{column}_text_backup"
                    
                    # 1. 添加临时text列
                    await conn.execute(text(f'ALTER TABLE "{schema}"."{table}" ADD COLUMN "{temp_column}" TEXT'))
                    logger.info(f"  ✓ 添加临时列 {temp_column}")
                    
                    # 2. 复制vector数据到text列（转换为字符串）
                    await conn.execute(text(f'''
                        UPDATE "{schema}"."{table}" 
                        SET "{temp_column}" = CASE 
                            WHEN "{column}" IS NULL THEN NULL
                            ELSE "{column}"::text
                        END
                    '''))
                    logger.info(f"  ✓ 复制数据到临时列")
                    
                    # 3. 删除原vector列
                    await conn.execute(text(f'ALTER TABLE "{schema}"."{table}" DROP COLUMN "{column}"'))
                    logger.info(f"  ✓ 删除原vector列")
                    
                    # 4. 重命名临时列为原列名
                    await conn.execute(text(f'ALTER TABLE "{schema}"."{table}" RENAME COLUMN "{temp_column}" TO "{column}"'))
                    logger.info(f"  ✓ 重命名列为原名")
                    
                    logger.info(f"✅ 成功转换 {schema}.{table}.{column}")
                    
                except Exception as e:
                    logger.error(f"❌ 转换失败 {schema}.{table}.{column}: {e}")
                    # 尝试清理临时列
                    try:
                        await conn.execute(text(f'ALTER TABLE "{schema}"."{table}" DROP COLUMN IF EXISTS "{temp_column}"'))
                    except:
                        pass
            
            # 验证转换结果
            result = await conn.execute(text("""
                SELECT COUNT(*) 
                FROM pg_attribute a
                JOIN pg_class c ON a.attrelid = c.oid
                JOIN pg_namespace n ON c.relnamespace = n.oid
                JOIN pg_type t ON a.atttypid = t.oid
                WHERE t.typname = 'vector'
                  AND a.attnum > 0
                  AND NOT a.attisdropped
                  AND n.nspname = 'public';
            """))
            
            remaining_vectors = result.scalar()
            
            if remaining_vectors == 0:
                logger.info("✅ 所有vector类型列已成功转换为text类型")
                return True
            else:
                logger.warning(f"⚠️ 仍有 {remaining_vectors} 个vector类型列未转换")
                return False
        
    except Exception as e:
        logger.error(f"❌ 修复失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    logger.info("🚀 开始OpenGauss vector类型简单修复...")
    
    try:
        success = asyncio.run(simple_vector_fix())
        
        if success:
            logger.info("✅ 修复完成！现在可以重启Letta服务器了")
            logger.info("运行命令: letta server")
        else:
            logger.error("❌ 修复未完全成功，请检查日志")
        
        return 0 if success else 1
    
    except Exception as e:
        logger.error(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
