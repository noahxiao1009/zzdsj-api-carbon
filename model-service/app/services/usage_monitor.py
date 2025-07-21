"""
模型使用统计和监控服务
负责记录、分析和监控模型调用情况
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from collections import defaultdict, deque
import time
import json
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """指标类型"""
    CALL_COUNT = "call_count"
    TOKEN_USAGE = "token_usage"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    COST = "cost"
    THROUGHPUT = "throughput"


class TimeWindow(str, Enum):
    """时间窗口"""
    MINUTE = "1m"
    HOUR = "1h"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1M"


@dataclass
class UsageRecord:
    """使用记录"""
    timestamp: datetime
    user_id: str
    provider_id: str
    model_id: str
    call_type: str  # chat, embedding, completion, etc.
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    cost: float
    success: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class MetricSnapshot:
    """指标快照"""
    timestamp: datetime
    metric_type: MetricType
    value: float
    tags: Dict[str, str]
    window: TimeWindow


class UsageMonitor:
    """使用监控器"""
    
    def __init__(self, max_records: int = 100000):
        self.max_records = max_records
        self.usage_records: deque = deque(maxlen=max_records)
        self.metrics_cache: Dict[str, List[MetricSnapshot]] = defaultdict(list)
        
        # 实时统计缓存
        self.realtime_stats = {
            "total_calls": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "avg_latency": 0.0,
            "error_count": 0,
            "last_updated": datetime.now()
        }
        
        # 按时间窗口的统计缓存
        self.windowed_stats: Dict[TimeWindow, Dict[str, Any]] = {
            TimeWindow.MINUTE: defaultdict(lambda: defaultdict(float)),
            TimeWindow.HOUR: defaultdict(lambda: defaultdict(float)),
            TimeWindow.DAY: defaultdict(lambda: defaultdict(float))
        }
        
        # 启动后台任务
        self._background_tasks = []
        self._start_background_tasks()
    
    def _start_background_tasks(self):
        """启动后台任务"""
        # 定期清理过期数据
        cleanup_task = asyncio.create_task(self._cleanup_expired_data())
        self._background_tasks.append(cleanup_task)
        
        # 定期计算聚合指标
        aggregation_task = asyncio.create_task(self._calculate_aggregated_metrics())
        self._background_tasks.append(aggregation_task)
    
    async def record_usage(self, usage_data: Dict[str, Any]) -> bool:
        """
        记录模型使用情况
        
        Args:
            usage_data: 使用数据
            
        Returns:
            是否记录成功
        """
        try:
            # 创建使用记录
            record = UsageRecord(
                timestamp=datetime.now(),
                user_id=usage_data.get("user_id", "anonymous"),
                provider_id=usage_data["provider_id"],
                model_id=usage_data["model_id"],
                call_type=usage_data.get("call_type", "chat"),
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
                latency_ms=usage_data.get("latency_ms", 0.0),
                cost=usage_data.get("cost", 0.0),
                success=usage_data.get("success", True),
                error_type=usage_data.get("error_type"),
                error_message=usage_data.get("error_message"),
                request_id=usage_data.get("request_id"),
                session_id=usage_data.get("session_id")
            )
            
            # 添加到记录队列
            self.usage_records.append(record)
            
            # 更新实时统计
            await self._update_realtime_stats(record)
            
            # 更新窗口统计
            await self._update_windowed_stats(record)
            
            logger.debug(f"使用记录已保存: {record.provider_id}:{record.model_id}")
            return True
            
        except Exception as e:
            logger.error(f"记录使用情况失败: {e}")
            return False
    
    async def _update_realtime_stats(self, record: UsageRecord):
        """更新实时统计"""
        try:
            self.realtime_stats["total_calls"] += 1
            self.realtime_stats["total_tokens"] += record.total_tokens
            self.realtime_stats["total_cost"] += record.cost
            
            if not record.success:
                self.realtime_stats["error_count"] += 1
            
            # 计算平均延迟（移动平均）
            current_avg = self.realtime_stats["avg_latency"]
            total_calls = self.realtime_stats["total_calls"]
            self.realtime_stats["avg_latency"] = (
                (current_avg * (total_calls - 1) + record.latency_ms) / total_calls
            )
            
            self.realtime_stats["last_updated"] = datetime.now()
            
        except Exception as e:
            logger.error(f"更新实时统计失败: {e}")
    
    async def _update_windowed_stats(self, record: UsageRecord):
        """更新窗口统计"""
        try:
            # 生成时间窗口键
            now = record.timestamp
            
            windows = {
                TimeWindow.MINUTE: now.replace(second=0, microsecond=0),
                TimeWindow.HOUR: now.replace(minute=0, second=0, microsecond=0),
                TimeWindow.DAY: now.replace(hour=0, minute=0, second=0, microsecond=0)
            }
            
            # 生成统计键
            keys = [
                "global",  # 全局统计
                f"provider:{record.provider_id}",  # 按提供商
                f"model:{record.provider_id}:{record.model_id}",  # 按模型
                f"user:{record.user_id}",  # 按用户
                f"type:{record.call_type}"  # 按调用类型
            ]
            
            # 更新各个时间窗口的统计
            for window, window_time in windows.items():
                window_key = window_time.isoformat()
                
                for key in keys:
                    stats = self.windowed_stats[window][window_key][key]
                    
                    # 更新各项指标
                    stats["calls"] = stats.get("calls", 0) + 1
                    stats["tokens"] = stats.get("tokens", 0) + record.total_tokens
                    stats["cost"] = stats.get("cost", 0.0) + record.cost
                    stats["latency_sum"] = stats.get("latency_sum", 0.0) + record.latency_ms
                    
                    if not record.success:
                        stats["errors"] = stats.get("errors", 0) + 1
            
        except Exception as e:
            logger.error(f"更新窗口统计失败: {e}")
    
    async def get_usage_stats(
        self,
        user_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
        time_window: TimeWindow = TimeWindow.DAY,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取使用统计
        
        Args:
            user_id: 用户ID筛选
            provider_id: 提供商ID筛选
            model_id: 模型ID筛选
            time_window: 时间窗口
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            统计数据
        """
        try:
            # 设置默认时间范围
            if not end_time:
                end_time = datetime.now()
            if not start_time:
                if time_window == TimeWindow.HOUR:
                    start_time = end_time - timedelta(hours=24)
                elif time_window == TimeWindow.DAY:
                    start_time = end_time - timedelta(days=30)
                else:
                    start_time = end_time - timedelta(days=7)
            
            # 筛选记录
            filtered_records = []
            for record in self.usage_records:
                if record.timestamp < start_time or record.timestamp > end_time:
                    continue
                
                if user_id and record.user_id != user_id:
                    continue
                
                if provider_id and record.provider_id != provider_id:
                    continue
                
                if model_id and record.model_id != model_id:
                    continue
                
                filtered_records.append(record)
            
            # 计算统计指标
            if not filtered_records:
                return {
                    "total_calls": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "avg_latency": 0.0,
                    "error_rate": 0.0,
                    "throughput": 0.0,
                    "time_series": [],
                    "breakdown": {}
                }
            
            # 基础统计
            total_calls = len(filtered_records)
            total_tokens = sum(r.total_tokens for r in filtered_records)
            total_cost = sum(r.cost for r in filtered_records)
            avg_latency = sum(r.latency_ms for r in filtered_records) / total_calls
            error_count = sum(1 for r in filtered_records if not r.success)
            error_rate = error_count / total_calls if total_calls > 0 else 0.0
            
            # 计算吞吐量（每分钟调用数）
            time_span_minutes = (end_time - start_time).total_seconds() / 60
            throughput = total_calls / time_span_minutes if time_span_minutes > 0 else 0.0
            
            # 时间序列数据
            time_series = await self._generate_time_series(
                filtered_records, time_window, start_time, end_time
            )
            
            # 分类统计
            breakdown = await self._generate_breakdown(filtered_records)
            
            return {
                "total_calls": total_calls,
                "total_tokens": total_tokens,
                "total_cost": round(total_cost, 4),
                "avg_latency": round(avg_latency, 2),
                "error_rate": round(error_rate, 4),
                "throughput": round(throughput, 2),
                "time_series": time_series,
                "breakdown": breakdown,
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "window": time_window
                }
            }
            
        except Exception as e:
            logger.error(f"获取使用统计失败: {e}")
            raise
    
    async def _generate_time_series(
        self,
        records: List[UsageRecord],
        time_window: TimeWindow,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """生成时间序列数据"""
        try:
            # 确定时间间隔
            if time_window == TimeWindow.MINUTE:
                interval = timedelta(minutes=1)
            elif time_window == TimeWindow.HOUR:
                interval = timedelta(hours=1)
            else:
                interval = timedelta(days=1)
            
            # 生成时间点
            time_points = []
            current_time = start_time
            while current_time <= end_time:
                time_points.append(current_time)
                current_time += interval
            
            # 按时间点聚合数据
            time_series = []
            for time_point in time_points:
                next_time = time_point + interval
                
                # 筛选该时间段的记录
                period_records = [
                    r for r in records
                    if time_point <= r.timestamp < next_time
                ]
                
                if period_records:
                    calls = len(period_records)
                    tokens = sum(r.total_tokens for r in period_records)
                    cost = sum(r.cost for r in period_records)
                    avg_latency = sum(r.latency_ms for r in period_records) / calls
                    errors = sum(1 for r in period_records if not r.success)
                else:
                    calls = tokens = cost = avg_latency = errors = 0
                
                time_series.append({
                    "timestamp": time_point.isoformat(),
                    "calls": calls,
                    "tokens": tokens,
                    "cost": round(cost, 4),
                    "avg_latency": round(avg_latency, 2),
                    "errors": errors
                })
            
            return time_series
            
        except Exception as e:
            logger.error(f"生成时间序列失败: {e}")
            return []
    
    async def _generate_breakdown(self, records: List[UsageRecord]) -> Dict[str, Any]:
        """生成分类统计"""
        try:
            breakdown = {
                "by_provider": defaultdict(lambda: {"calls": 0, "tokens": 0, "cost": 0.0}),
                "by_model": defaultdict(lambda: {"calls": 0, "tokens": 0, "cost": 0.0}),
                "by_user": defaultdict(lambda: {"calls": 0, "tokens": 0, "cost": 0.0}),
                "by_call_type": defaultdict(lambda: {"calls": 0, "tokens": 0, "cost": 0.0})
            }
            
            for record in records:
                # 按提供商
                provider_stats = breakdown["by_provider"][record.provider_id]
                provider_stats["calls"] += 1
                provider_stats["tokens"] += record.total_tokens
                provider_stats["cost"] += record.cost
                
                # 按模型
                model_key = f"{record.provider_id}:{record.model_id}"
                model_stats = breakdown["by_model"][model_key]
                model_stats["calls"] += 1
                model_stats["tokens"] += record.total_tokens
                model_stats["cost"] += record.cost
                
                # 按用户
                user_stats = breakdown["by_user"][record.user_id]
                user_stats["calls"] += 1
                user_stats["tokens"] += record.total_tokens
                user_stats["cost"] += record.cost
                
                # 按调用类型
                type_stats = breakdown["by_call_type"][record.call_type]
                type_stats["calls"] += 1
                type_stats["tokens"] += record.total_tokens
                type_stats["cost"] += record.cost
            
            # 转换为普通字典并排序
            result = {}
            for category, data in breakdown.items():
                sorted_data = sorted(
                    data.items(),
                    key=lambda x: x[1]["calls"],
                    reverse=True
                )
                result[category] = [
                    {"key": k, **v} for k, v in sorted_data[:10]  # 只返回前10个
                ]
            
            return result
            
        except Exception as e:
            logger.error(f"生成分类统计失败: {e}")
            return {}
    
    async def get_realtime_metrics(self) -> Dict[str, Any]:
        """获取实时指标"""
        try:
            stats = self.realtime_stats.copy()
            
            # 计算错误率
            error_rate = (
                stats["error_count"] / stats["total_calls"]
                if stats["total_calls"] > 0 else 0.0
            )
            
            # 计算每分钟调用数（基于最近的记录）
            now = datetime.now()
            recent_records = [
                r for r in self.usage_records
                if (now - r.timestamp).total_seconds() <= 60
            ]
            calls_per_minute = len(recent_records)
            
            return {
                "total_calls": stats["total_calls"],
                "total_tokens": stats["total_tokens"],
                "total_cost": round(stats["total_cost"], 4),
                "avg_latency": round(stats["avg_latency"], 2),
                "error_count": stats["error_count"],
                "error_rate": round(error_rate, 4),
                "calls_per_minute": calls_per_minute,
                "last_updated": stats["last_updated"].isoformat(),
                "active_records": len(self.usage_records)
            }
            
        except Exception as e:
            logger.error(f"获取实时指标失败: {e}")
            return {}
    
    async def get_top_models(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取使用最多的模型"""
        try:
            model_stats = defaultdict(lambda: {
                "calls": 0,
                "tokens": 0,
                "cost": 0.0,
                "avg_latency": 0.0,
                "error_count": 0
            })
            
            # 统计各模型使用情况
            for record in self.usage_records:
                model_key = f"{record.provider_id}:{record.model_id}"
                stats = model_stats[model_key]
                
                stats["calls"] += 1
                stats["tokens"] += record.total_tokens
                stats["cost"] += record.cost
                stats["avg_latency"] = (
                    (stats["avg_latency"] * (stats["calls"] - 1) + record.latency_ms) / stats["calls"]
                )
                
                if not record.success:
                    stats["error_count"] += 1
            
            # 排序并返回前N个
            sorted_models = sorted(
                model_stats.items(),
                key=lambda x: x[1]["calls"],
                reverse=True
            )
            
            result = []
            for model_key, stats in sorted_models[:limit]:
                provider_id, model_id = model_key.split(":", 1)
                result.append({
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "calls": stats["calls"],
                    "tokens": stats["tokens"],
                    "cost": round(stats["cost"], 4),
                    "avg_latency": round(stats["avg_latency"], 2),
                    "error_rate": round(stats["error_count"] / stats["calls"], 4) if stats["calls"] > 0 else 0.0
                })
            
            return result
            
        except Exception as e:
            logger.error(f"获取热门模型失败: {e}")
            return []
    
    async def _cleanup_expired_data(self):
        """清理过期数据"""
        while True:
            try:
                await asyncio.sleep(3600)  # 每小时清理一次
                
                # 清理过期的窗口统计（保留7天）
                cutoff_time = datetime.now() - timedelta(days=7)
                
                for window in self.windowed_stats:
                    expired_keys = [
                        key for key in self.windowed_stats[window]
                        if datetime.fromisoformat(key) < cutoff_time
                    ]
                    
                    for key in expired_keys:
                        del self.windowed_stats[window][key]
                
                logger.info("过期数据清理完成")
                
            except Exception as e:
                logger.error(f"清理过期数据失败: {e}")
    
    async def _calculate_aggregated_metrics(self):
        """计算聚合指标"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟计算一次
                
                # 计算各种聚合指标
                # TODO: 实现更复杂的聚合计算
                
                logger.debug("聚合指标计算完成")
                
            except Exception as e:
                logger.error(f"计算聚合指标失败: {e}")
    
    async def export_usage_data(
        self,
        format_type: str = "json",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Union[str, bytes]:
        """
        导出使用数据
        
        Args:
            format_type: 导出格式 (json, csv)
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            导出的数据
        """
        try:
            # 筛选记录
            if not start_time:
                start_time = datetime.now() - timedelta(days=30)
            if not end_time:
                end_time = datetime.now()
            
            filtered_records = [
                record for record in self.usage_records
                if start_time <= record.timestamp <= end_time
            ]
            
            if format_type.lower() == "json":
                data = [asdict(record) for record in filtered_records]
                # 转换datetime为字符串
                for item in data:
                    item["timestamp"] = item["timestamp"].isoformat()
                return json.dumps(data, indent=2, ensure_ascii=False)
            
            elif format_type.lower() == "csv":
                import csv
                import io
                
                output = io.StringIO()
                if filtered_records:
                    fieldnames = asdict(filtered_records[0]).keys()
                    writer = csv.DictWriter(output, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for record in filtered_records:
                        row = asdict(record)
                        row["timestamp"] = row["timestamp"].isoformat()
                        writer.writerow(row)
                
                return output.getvalue()
            
            else:
                raise ValueError(f"不支持的导出格式: {format_type}")
                
        except Exception as e:
            logger.error(f"导出使用数据失败: {e}")
            raise


# 全局使用监控器实例
usage_monitor = UsageMonitor()