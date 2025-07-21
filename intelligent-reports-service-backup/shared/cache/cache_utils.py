"""
缓存工具函数
提供键生成、序列化、哈希等工具函数
"""

import json
import pickle
import hashlib
import gzip
from typing import Any, Dict, List, Optional, Union
from .cache_config import SERVICE_NAME_MAPPING, CACHE_TYPE_MAPPING, CacheConfig


def generate_cache_key(
    service: str, 
    cache_type: str, 
    identifier: str,
    sub_key: Optional[str] = None
) -> str:
    """
    生成标准化的缓存键
    格式: unified:{service}:{type}:{id}[:{sub_key}]
    """
    # 映射服务名称
    service_short = SERVICE_NAME_MAPPING.get(service, service)
    
    # 映射缓存类型
    type_short = CACHE_TYPE_MAPPING.get(cache_type, cache_type)
    
    # 构建基础键
    parts = [CacheConfig.KEY_PREFIX, service_short, type_short, str(identifier)]
    
    # 添加子键
    if sub_key:
        parts.append(str(sub_key))
    
    return CacheConfig.KEY_SEPARATOR.join(parts)


def hash_params(*args, **kwargs) -> str:
    """生成参数的哈希值，用于缓存键的唯一标识"""
    # 创建参数字典
    params = {
        'args': args,
        'kwargs': sorted(kwargs.items()) if kwargs else {}
    }
    
    # 序列化参数
    params_str = json.dumps(params, sort_keys=True, ensure_ascii=False)
    
    # 生成哈希
    return hashlib.md5(params_str.encode('utf-8')).hexdigest()


def serialize_value(
    value: Any, 
    method: str = "json",
    compress: bool = False,
    compress_threshold: int = 1024
) -> Union[str, bytes]:
    """序列化值用于Redis存储"""
    # 序列化
    if method == "json":
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        data = serialized.encode('utf-8')
    elif method == "pickle":
        data = pickle.dumps(value)
    else:
        raise ValueError(f"不支持的序列化方法: {method}")
    
    # 压缩处理
    if compress and len(data) > compress_threshold:
        data = gzip.compress(data)
        # 添加压缩标记
        if method == "json":
            return b"compressed:" + data
        else:
            return b"compressed_pickle:" + data
    
    return data.decode('utf-8') if method == "json" else data


def deserialize_value(
    data: Union[str, bytes], 
    method: str = "json"
) -> Any:
    """反序列化Redis中的值"""
    if data is None:
        return None
    
    # 处理压缩数据
    if isinstance(data, bytes):
        if data.startswith(b"compressed:"):
            # JSON压缩数据
            compressed_data = data[11:]  # 移除"compressed:"前缀
            decompressed = gzip.decompress(compressed_data)
            return json.loads(decompressed.decode('utf-8'))
        elif data.startswith(b"compressed_pickle:"):
            # Pickle压缩数据
            compressed_data = data[18:]  # 移除"compressed_pickle:"前缀
            decompressed = gzip.decompress(compressed_data)
            return pickle.loads(decompressed)
        elif method == "pickle":
            # 未压缩的pickle数据
            return pickle.loads(data)
    
    # 处理字符串数据
    if isinstance(data, str):
        if method == "json":
            return json.loads(data)
        else:
            # 可能是编码的pickle数据
            return pickle.loads(data.encode('utf-8'))
    
    return data
