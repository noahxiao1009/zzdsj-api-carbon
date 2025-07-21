"""
统一状态管理测试
验证ProcessStatus枚举、RetryMixin类和状态转换逻辑的正确性
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import patch

from process_status import (
    ProcessStatus,
    RetryStrategy,
    RetryConfig,
    RetryMixin,
    ErrorInfo,
    StatusTransitionValidator,
    StatusMigration,
    validate_status_transition,
    create_standard_response,
    get_status_priority
)


class TestProcessStatus:
    """测试ProcessStatus枚举"""
    
    def test_status_states(self):
        """测试状态分类"""
        # 测试待处理状态
        assert ProcessStatus.is_pending_state(ProcessStatus.PENDING)
        assert not ProcessStatus.is_pending_state(ProcessStatus.PROCESSING)
        
        # 测试活跃状态
        assert ProcessStatus.is_active_state(ProcessStatus.PROCESSING)
        assert ProcessStatus.is_active_state(ProcessStatus.RETRYING)
        assert not ProcessStatus.is_active_state(ProcessStatus.PENDING)
        
        # 测试终态
        assert ProcessStatus.is_terminal_state(ProcessStatus.COMPLETED)
        assert ProcessStatus.is_terminal_state(ProcessStatus.FAILED)
        assert not ProcessStatus.is_terminal_state(ProcessStatus.PROCESSING)
        
        # 测试成功状态
        assert ProcessStatus.is_success_state(ProcessStatus.COMPLETED)
        assert not ProcessStatus.is_success_state(ProcessStatus.FAILED)
        
        # 测试失败状态
        assert ProcessStatus.is_failure_state(ProcessStatus.FAILED)
        assert ProcessStatus.is_failure_state(ProcessStatus.TIMEOUT)
        assert not ProcessStatus.is_failure_state(ProcessStatus.COMPLETED)
    
    def test_status_transitions(self):
        """测试状态转换规则"""
        # 有效转换
        assert ProcessStatus.can_transition_to(ProcessStatus.PENDING, ProcessStatus.PROCESSING)
        assert ProcessStatus.can_transition_to(ProcessStatus.PROCESSING, ProcessStatus.COMPLETED)
        assert ProcessStatus.can_transition_to(ProcessStatus.PROCESSING, ProcessStatus.FAILED)
        assert ProcessStatus.can_transition_to(ProcessStatus.PROCESSING, ProcessStatus.RETRYING)
        assert ProcessStatus.can_transition_to(ProcessStatus.RETRYING, ProcessStatus.PROCESSING)
        
        # 无效转换（终态不能转换）
        assert not ProcessStatus.can_transition_to(ProcessStatus.COMPLETED, ProcessStatus.PROCESSING)
        assert not ProcessStatus.can_transition_to(ProcessStatus.FAILED, ProcessStatus.PENDING)
        assert not ProcessStatus.can_transition_to(ProcessStatus.CANCELLED, ProcessStatus.PROCESSING)


class TestRetryConfig:
    """测试重试配置"""
    
    def test_fixed_delay(self):
        """测试固定延迟策略"""
        config = RetryConfig(strategy=RetryStrategy.FIXED, base_delay=5.0, jitter=False)
        
        assert config.calculate_delay(0) == 5.0
        assert config.calculate_delay(1) == 5.0
        assert config.calculate_delay(5) == 5.0
    
    def test_linear_delay(self):
        """测试线性延迟策略"""
        config = RetryConfig(strategy=RetryStrategy.LINEAR, base_delay=2.0, jitter=False)
        
        assert config.calculate_delay(0) == 2.0  # 2.0 * (0 + 1)
        assert config.calculate_delay(1) == 4.0  # 2.0 * (1 + 1)
        assert config.calculate_delay(2) == 6.0  # 2.0 * (2 + 1)
    
    def test_exponential_delay(self):
        """测试指数延迟策略"""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL, 
            base_delay=1.0, 
            backoff_factor=2.0,
            jitter=False
        )
        
        assert config.calculate_delay(0) == 1.0  # 1.0 * (2.0 ^ 0)
        assert config.calculate_delay(1) == 2.0  # 1.0 * (2.0 ^ 1)
        assert config.calculate_delay(2) == 4.0  # 1.0 * (2.0 ^ 2)
    
    def test_max_delay_limit(self):
        """测试最大延迟限制"""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay=10.0,
            max_delay=15.0,
            backoff_factor=2.0,
            jitter=False
        )
        
        assert config.calculate_delay(0) == 10.0
        assert config.calculate_delay(1) <= 15.0
        assert config.calculate_delay(2) <= 15.0  # 应该被限制在15.0
    
    def test_jitter(self):
        """测试随机抖动"""
        config = RetryConfig(strategy=RetryStrategy.FIXED, base_delay=10.0, jitter=True)
        
        # 测试多次，确保有随机性
        delays = [config.calculate_delay(0) for _ in range(10)]
        
        # 所有延迟应该在 5.0 到 10.0 之间（抖动范围）
        for delay in delays:
            assert 5.0 <= delay <= 10.0
        
        # 应该有不同的值（随机性）
        assert len(set(delays)) > 1


class TestErrorInfo:
    """测试错误信息"""
    
    def test_error_info_creation(self):
        """测试错误信息创建"""
        error = ErrorInfo(
            error_type="ValueError",
            error_message="测试错误",
            error_code="E001"
        )
        
        assert error.error_type == "ValueError"
        assert error.error_message == "测试错误"
        assert error.error_code == "E001"
        assert isinstance(error.occurred_at, datetime)
    
    def test_error_info_to_dict(self):
        """测试错误信息转换为字典"""
        error = ErrorInfo(
            error_type="ValueError",
            error_message="测试错误",
            context={"user_id": 123}
        )
        
        result = error.to_dict()
        
        assert result["error_type"] == "ValueError"
        assert result["error_message"] == "测试错误"
        assert result["context"]["user_id"] == 123
        assert "occurred_at" in result


class TestRetryMixin:
    """测试重试机制"""
    
    class MockTask(RetryMixin):
        """模拟任务类"""
        
        def __init__(self, max_retries=3):
            super().__init__()
            self.max_retries = max_retries
    
    def test_initial_state(self):
        """测试初始状态"""
        task = self.MockTask()
        
        assert task.retry_count == 0
        assert task.status == ProcessStatus.PENDING
        assert task.last_retry_at is None
        assert task.next_retry_at is None
        assert len(task.error_history) == 0
    
    def test_can_retry(self):
        """测试重试条件"""
        task = self.MockTask(max_retries=2)
        
        # 初始状态不能重试（需要先失败）
        assert not task.can_retry()
        
        # 失败状态可以重试
        task.status = ProcessStatus.FAILED
        assert task.can_retry()
        
        # 达到最大重试次数后不能重试
        task.retry_count = 2
        assert not task.can_retry()
        
        # 完成状态不能重试
        task.retry_count = 0
        task.status = ProcessStatus.COMPLETED
        assert not task.can_retry()
    
    def test_schedule_retry(self):
        """测试调度重试"""
        task = self.MockTask()
        task.status = ProcessStatus.FAILED
        
        # 调度重试
        next_retry = task.schedule_retry()
        
        assert isinstance(next_retry, datetime)
        assert task.next_retry_at is not None
        assert task.last_retry_at is not None
        assert next_retry > datetime.now()
    
    def test_start_retry(self):
        """测试开始重试"""
        task = self.MockTask()
        task.status = ProcessStatus.FAILED
        
        initial_count = task.retry_count
        task.start_retry()
        
        assert task.retry_count == initial_count + 1
        assert task.status == ProcessStatus.RETRYING
        assert task.last_retry_at is not None
    
    def test_add_error(self):
        """测试添加错误"""
        task = self.MockTask()
        
        # 添加异常
        try:
            raise ValueError("测试错误")
        except ValueError as e:
            task.add_error(e)
        
        assert len(task.error_history) == 1
        assert task.error_history[0].error_type == "ValueError"
        assert task.error_history[0].error_message == "测试错误"
        
        # 添加字符串错误
        task.add_error("另一个错误")
        assert len(task.error_history) == 2
        assert task.error_history[1].error_message == "另一个错误"
    
    def test_error_history_limit(self):
        """测试错误历史限制"""
        task = self.MockTask()
        
        # 添加超过10个错误
        for i in range(15):
            task.add_error(f"错误 {i}")
        
        # 应该只保留最近的10个
        assert len(task.error_history) == 10
        assert task.error_history[0].error_message == "错误 5"  # 前5个被删除
        assert task.error_history[-1].error_message == "错误 14"
    
    def test_get_retry_stats(self):
        """测试获取重试统计"""
        task = self.MockTask()
        task.status = ProcessStatus.FAILED
        task.retry_count = 1
        task.add_error("测试错误")
        
        stats = task.get_retry_stats()
        
        assert stats["retry_count"] == 1
        assert stats["max_retries"] == 3
        assert stats["can_retry"] is True
        assert stats["error_count"] == 1
        assert "retry_config" in stats


class TestStatusTransitionValidator:
    """测试状态转换验证器"""
    
    class MockObject:
        def __init__(self):
            self.status = ProcessStatus.PENDING
    
    def test_validate_transition(self):
        """测试转换验证"""
        assert StatusTransitionValidator.validate_transition(
            ProcessStatus.PENDING, ProcessStatus.PROCESSING
        )
        assert not StatusTransitionValidator.validate_transition(
            ProcessStatus.COMPLETED, ProcessStatus.PROCESSING
        )
    
    def test_enforce_transition(self):
        """测试强制转换验证"""
        obj = self.MockObject()
        
        # 有效转换
        StatusTransitionValidator.enforce_transition(obj, ProcessStatus.PROCESSING)
        assert obj.status == ProcessStatus.PROCESSING
        
        # 无效转换应该抛出异常
        obj.status = ProcessStatus.COMPLETED
        with pytest.raises(ValueError, match="无效的状态转换"):
            StatusTransitionValidator.enforce_transition(obj, ProcessStatus.PROCESSING)


class TestStatusMigration:
    """测试状态迁移"""
    
    def test_migrate_status(self):
        """测试状态迁移"""
        # 测试常见映射
        assert StatusMigration.migrate_status("todo") == ProcessStatus.PENDING
        assert StatusMigration.migrate_status("running") == ProcessStatus.PROCESSING
        assert StatusMigration.migrate_status("done") == ProcessStatus.COMPLETED
        assert StatusMigration.migrate_status("error") == ProcessStatus.FAILED
        assert StatusMigration.migrate_status("cancelled") == ProcessStatus.CANCELLED
        
        # 测试大小写不敏感
        assert StatusMigration.migrate_status("TODO") == ProcessStatus.PENDING
        assert StatusMigration.migrate_status("Running") == ProcessStatus.PROCESSING
        
        # 测试未知状态默认映射
        assert StatusMigration.migrate_status("unknown") == ProcessStatus.PENDING
    
    def test_is_compatible_status(self):
        """测试状态兼容性"""
        # 标准状态
        assert StatusMigration.is_compatible_status(ProcessStatus.PENDING)
        assert StatusMigration.is_compatible_status(ProcessStatus.COMPLETED)
        
        # 可映射的旧状态
        assert StatusMigration.is_compatible_status("todo")
        assert StatusMigration.is_compatible_status("running")
        
        # 大小写不敏感
        assert StatusMigration.is_compatible_status("TODO")
        
        # 完全未知的状态
        assert not StatusMigration.is_compatible_status("completely_unknown")


class TestUtilityFunctions:
    """测试实用函数"""
    
    def test_create_standard_response(self):
        """测试创建标准响应"""
        # 成功响应
        response = create_standard_response(
            success=True,
            message="操作成功",
            data={"result": "test"}
        )
        
        assert response["success"] is True
        assert response["message"] == "操作成功"
        assert response["data"]["result"] == "test"
        assert response["status"] == ProcessStatus.COMPLETED
        assert "timestamp" in response
        
        # 失败响应
        error = ErrorInfo(error_message="测试错误")
        response = create_standard_response(
            success=False,
            message="操作失败",
            error_info=error,
            status=ProcessStatus.FAILED
        )
        
        assert response["success"] is False
        assert response["status"] == ProcessStatus.FAILED
        assert "error" in response
        assert response["error"]["error_message"] == "测试错误"
    
    def test_get_status_priority(self):
        """测试状态优先级"""
        # 失败状态优先级最高
        assert get_status_priority(ProcessStatus.FAILED) == 1
        assert get_status_priority(ProcessStatus.TIMEOUT) == 2
        
        # 处理中状态
        assert get_status_priority(ProcessStatus.RETRYING) == 3
        assert get_status_priority(ProcessStatus.PROCESSING) == 4
        
        # 待处理状态
        assert get_status_priority(ProcessStatus.PENDING) == 5
        
        # 完成状态
        assert get_status_priority(ProcessStatus.COMPLETED) == 6
        
        # 取消和跳过状态
        assert get_status_priority(ProcessStatus.CANCELLED) == 7
        assert get_status_priority(ProcessStatus.SKIPPED) == 8
        
        # 未知状态
        assert get_status_priority("unknown") == 999


class TestValidateStatusTransitionDecorator:
    """测试状态转换验证装饰器"""
    
    class MockService:
        def __init__(self):
            self.status = ProcessStatus.PENDING
        
        @validate_status_transition
        def update_status(self, new_status: str):
            self.status = new_status
        
        @validate_status_transition
        def update_with_kwargs(self, **kwargs):
            if 'status' in kwargs:
                self.status = kwargs['status']
    
    def test_valid_transition_with_decorator(self):
        """测试装饰器的有效转换"""
        service = self.MockService()
        
        # 有效转换
        service.update_status(ProcessStatus.PROCESSING)
        assert service.status == ProcessStatus.PROCESSING
        
        service.update_status(ProcessStatus.COMPLETED)
        assert service.status == ProcessStatus.COMPLETED
    
    def test_invalid_transition_with_decorator(self):
        """测试装饰器的无效转换"""
        service = self.MockService()
        service.status = ProcessStatus.COMPLETED  # 设置为终态
        
        # 尝试无效转换
        with pytest.raises(ValueError, match="无效的状态转换"):
            service.update_status(ProcessStatus.PROCESSING)
    
    def test_decorator_with_kwargs(self):
        """测试装饰器与关键字参数"""
        service = self.MockService()
        
        # 通过kwargs更新状态
        service.update_with_kwargs(status=ProcessStatus.PROCESSING)
        assert service.status == ProcessStatus.PROCESSING


if __name__ == "__main__":
    # 运行基本测试
    test_classes = [
        TestProcessStatus,
        TestRetryConfig,
        TestErrorInfo,
        TestRetryMixin,
        TestStatusTransitionValidator,
        TestStatusMigration,
        TestUtilityFunctions,
        TestValidateStatusTransitionDecorator
    ]
    
    print("运行统一状态管理测试...")
    
    for test_class in test_classes:
        print(f"\n测试 {test_class.__name__}:")
        test_instance = test_class()
        
        # 运行所有测试方法
        for method_name in dir(test_instance):
            if method_name.startswith('test_'):
                try:
                    method = getattr(test_instance, method_name)
                    method()
                    print(f"  ✅ {method_name}")
                except Exception as e:
                    print(f"  ❌ {method_name}: {e}")
    
    print("\n✅ 统一状态管理测试完成！") 