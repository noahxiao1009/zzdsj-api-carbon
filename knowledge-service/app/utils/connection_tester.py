"""
连接测试工具
适配本地和远程环境的不同连接验证需求
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
import psycopg2
import redis
from elasticsearch import Elasticsearch

from app.config.settings import settings

logger = logging.getLogger(__name__)


class ConnectionTester:
    """连接测试器，适配不同环境"""
    
    def __init__(self, config_settings: Optional[Any] = None):
        self.settings = config_settings or settings
        self.test_config = self.settings.get_connection_test_config()
    
    async def test_postgresql(self) -> Dict[str, Any]:
        """测试PostgreSQL连接"""
        start_time = time.time()
        
        try:
            db_config = self.settings.get_database_config()
            
            # 构建连接字符串
            conn_params = {
                "host": db_config["host"],
                "port": db_config["port"],
                "database": db_config["database"],
                "user": db_config["user"],
                "connect_timeout": self.test_config["database_timeout"]
            }
            
            # 本地环境可能不需要密码
            if "password" in db_config and db_config["password"]:
                conn_params["password"] = db_config["password"]
            
            # 测试连接
            conn = psycopg2.connect(**conn_params)
            
            # 简单查询测试
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            elapsed = time.time() - start_time
            
            return {
                "status": "success",
                "message": "PostgreSQL连接成功",
                "version": version[:50] + "..." if len(version) > 50 else version,
                "response_time": round(elapsed, 3),
                "environment": "local" if self.settings.is_local else "remote"
            }
            
        except Exception as e:
            elapsed = time.time() - start_time
            
            # 本地环境提供更详细的错误信息
            error_detail = str(e) if self.settings.is_local else "连接失败"
            
            return {
                "status": "error",
                "message": f"PostgreSQL连接失败: {error_detail}",
                "response_time": round(elapsed, 3),
                "environment": "local" if self.settings.is_local else "remote"
            }
    
    async def test_redis(self) -> Dict[str, Any]:
        """测试Redis连接"""
        start_time = time.time()
        
        try:
            redis_url = self.settings.get_redis_url()
            
            # 创建Redis连接
            r = redis.from_url(
                redis_url,
                socket_connect_timeout=self.test_config["redis_timeout"],
                socket_timeout=self.test_config["redis_timeout"]
            )
            
            # 测试连接
            result = r.ping()
            info = r.info("server")
            
            r.close()
            
            elapsed = time.time() - start_time
            
            return {
                "status": "success",
                "message": "Redis连接成功",
                "version": info.get("redis_version", "unknown"),
                "response_time": round(elapsed, 3),
                "environment": "local" if self.settings.is_local else "remote"
            }
            
        except Exception as e:
            elapsed = time.time() - start_time
            
            error_detail = str(e) if self.settings.is_local else "连接失败"
            
            return {
                "status": "error",
                "message": f"Redis连接失败: {error_detail}",
                "response_time": round(elapsed, 3),
                "environment": "local" if self.settings.is_local else "remote"
            }
    
    async def test_elasticsearch(self) -> Dict[str, Any]:
        """测试Elasticsearch连接"""
        if not self.settings.vector_store.elasticsearch_enabled:
            return {
                "status": "disabled",
                "message": "Elasticsearch未启用",
                "environment": "local" if self.settings.is_local else "remote"
            }
        
        start_time = time.time()
        
        try:
            es_config = self.settings.get_elasticsearch_config()
            
            # 本地环境简化配置
            if self.settings.is_local:
                es_config.update({
                    "request_timeout": self.test_config["elasticsearch_timeout"],
                    "max_retries": 1,
                    "retry_on_timeout": False
                })
            else:
                es_config.update({
                    "request_timeout": self.test_config["elasticsearch_timeout"],
                    "max_retries": 3,
                    "retry_on_timeout": True
                })
            
            # 创建ES客户端
            es = Elasticsearch(**es_config)
            
            # 测试连接
            info = es.info()
            
            elapsed = time.time() - start_time
            
            return {
                "status": "success",
                "message": "Elasticsearch连接成功",
                "version": info["version"]["number"],
                "cluster_name": info["cluster_name"],
                "response_time": round(elapsed, 3),
                "environment": "local" if self.settings.is_local else "remote"
            }
            
        except Exception as e:
            elapsed = time.time() - start_time
            
            error_detail = str(e) if self.settings.is_local else "连接失败"
            
            return {
                "status": "error",
                "message": f"Elasticsearch连接失败: {error_detail}",
                "response_time": round(elapsed, 3),
                "environment": "local" if self.settings.is_local else "remote"
            }
    
    async def test_all_connections(self) -> Dict[str, Any]:
        """测试所有连接"""
        logger.info(f"开始连接测试 - 环境: {'本地' if self.settings.is_local else '远程'}")
        
        start_time = time.time()
        
        # 并发测试所有连接
        postgres_task = asyncio.create_task(self.test_postgresql())
        redis_task = asyncio.create_task(self.test_redis())
        es_task = asyncio.create_task(self.test_elasticsearch())
        
        postgres_result = await postgres_task
        redis_result = await redis_task
        es_result = await es_task
        
        total_time = time.time() - start_time
        
        # 统计结果
        all_results = [postgres_result, redis_result]
        if es_result["status"] != "disabled":
            all_results.append(es_result)
        
        success_count = sum(1 for r in all_results if r["status"] == "success")
        total_services = len(all_results)
        
        overall_status = "success" if success_count == total_services else "partial" if success_count > 0 else "error"
        
        return {
            "overall_status": overall_status,
            "environment": "local" if self.settings.is_local else "remote",
            "summary": f"{success_count}/{total_services} 服务连接成功",
            "total_time": round(total_time, 3),
            "services": {
                "postgresql": postgres_result,
                "redis": redis_result,
                "elasticsearch": es_result
            },
            "recommendations": self._get_recommendations(postgres_result, redis_result, es_result)
        }
    
    def _get_recommendations(self, postgres_result: Dict, redis_result: Dict, es_result: Dict) -> list:
        """根据测试结果提供建议"""
        recommendations = []
        
        if postgres_result["status"] == "error":
            if self.settings.is_local:
                recommendations.append("请确保本地PostgreSQL服务已启动: brew services start postgresql")
            else:
                recommendations.append("请检查远程PostgreSQL连接配置和网络连通性")
        
        if redis_result["status"] == "error":
            if self.settings.is_local:
                recommendations.append("请确保本地Redis服务已启动: brew services start redis")
            else:
                recommendations.append("请检查Redis连接配置")
        
        if es_result["status"] == "error":
            if self.settings.is_local:
                recommendations.append("请确保本地Elasticsearch服务已启动")
            else:
                recommendations.append("请检查Elasticsearch连接配置和认证信息")
        
        # 性能建议
        if any(r.get("response_time", 0) > 5 for r in [postgres_result, redis_result, es_result]):
            recommendations.append("检测到连接延迟较高，建议检查网络连接或使用本地环境进行开发")
        
        return recommendations


# 全局连接测试器实例
connection_tester = ConnectionTester()


async def quick_health_check() -> bool:
    """快速健康检查，返回是否所有核心服务可用"""
    try:
        results = await connection_tester.test_all_connections()
        return results["overall_status"] in ["success", "partial"]
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return False