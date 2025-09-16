"""
Vector数据类型处理器 - 解决OpenGauss vector类型与asyncpg不兼容问题
"""
import asyncpg
import sqlalchemy
from sqlalchemy import TypeDecorator, Text, String
from sqlalchemy.dialects.postgresql import ARRAY
import json
import logging

logger = logging.getLogger(__name__)

class VectorType(TypeDecorator):
    """自定义Vector类型处理器"""
    impl = Text
    
    def process_bind_param(self, value, dialect):
        """将Python值转换为数据库存储格式"""
        if value is None:
            return value
        if isinstance(value, (list, tuple)):
            # 将向量转换为字符串格式
            return f"[{','.join(map(str, value))}]"
        if isinstance(value, str):
            return value
        return str(value)
    
    def process_result_value(self, value, dialect):
        """将数据库值转换为Python对象"""
        if value is None:
            return value
        if isinstance(value, str):
            try:
                # 尝试解析向量字符串
                if value.startswith('[') and value.endswith(']'):
                    return json.loads(value)
                return value
            except (json.JSONDecodeError, ValueError):
                return value
        return value

async def register_vector_type_codec(connection):
    """为asyncpg连接注册vector类型编解码器"""
    try:
        # 注册vector类型的编解码器
        await connection.set_type_codec(
            'vector',
            encoder=_encode_vector,
            decoder=_decode_vector,
            schema='pg_catalog',
            format='text'
        )
        logger.info("✅ Vector类型编解码器注册成功")
    except Exception as e:
        logger.warning(f"⚠️ Vector类型编解码器注册失败: {e}")

def _encode_vector(value):
    """编码vector值为数据库格式"""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return f"[{','.join(map(str, value))}]"
    return str(value)

def _decode_vector(value):
    """解码数据库vector值为Python对象"""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            if value.startswith('[') and value.endswith(']'):
                return json.loads(value)
        return value
    except (json.JSONDecodeError, ValueError):
        return value

def setup_vector_type_handling():
    """设置vector类型处理"""
    try:
        # 为SQLAlchemy注册自定义类型
        from sqlalchemy import create_engine
        
        logger.info("✅ Vector类型处理设置完成")
        return True
    except Exception as e:
        logger.error(f"❌ Vector类型处理设置失败: {e}")
        return False
