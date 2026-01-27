"""
自适应限速器 + 熔断器
Token 限速与熔断保护
"""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"       # 正常
    OPEN = "open"           # 熔断
    HALF_OPEN = "half_open" # 探测


@dataclass
class RateLimitConfig:
    """限速配置"""
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000
    burst_multiplier: float = 1.5
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: int = 60


class CircuitBreakerOpen(Exception):
    """熔断器打开异常"""
    def __init__(self, message: str = "Circuit breaker is open"):
        super().__init__(message)


class TokenQuotaExceeded(Exception):
    """Token 配额超出异常"""
    def __init__(self, requested: int, available: int):
        super().__init__(f"Token quota exceeded: requested {requested}, available {available}")


class AdaptiveRateLimiter:
    """自适应限速器 + 熔断器"""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.request_semaphore = asyncio.Semaphore(
            int(config.requests_per_minute * config.burst_multiplier)
        )
        self.token_bucket = config.tokens_per_minute
        self.consecutive_failures = 0
        self.circuit_state = CircuitState.CLOSED
        self.last_failure_time: Optional[datetime] = None
        self._lock = asyncio.Lock()
        self._last_estimated = 0
        
        # 启动 token 补充任务
        self._replenish_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动限速器"""
        self._replenish_task = asyncio.create_task(self._replenish_tokens())

    async def stop(self):
        """停止限速器"""
        if self._replenish_task:
            self._replenish_task.cancel()
            try:
                await self._replenish_task
            except asyncio.CancelledError:
                pass

    async def _replenish_tokens(self):
        """定期补充 token"""
        while True:
            await asyncio.sleep(1)  # 每秒补充
            async with self._lock:
                # 每秒补充 tokens_per_minute / 60 个 token
                replenish_amount = self.config.tokens_per_minute / 60
                self.token_bucket = min(
                    self.config.tokens_per_minute,
                    self.token_bucket + replenish_amount
                )

    async def acquire(self, estimated_tokens: int) -> bool:
        """获取执行许可"""
        async with self._lock:
            # 检查熔断状态
            if self.circuit_state == CircuitState.OPEN:
                if self._should_try_recovery():
                    self.circuit_state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker entering HALF_OPEN state")
                else:
                    raise CircuitBreakerOpen("LLM service circuit is open")

            # 检查 Token 配额
            if self.token_bucket < estimated_tokens:
                raise TokenQuotaExceeded(estimated_tokens, int(self.token_bucket))

            self.token_bucket -= estimated_tokens
            self._last_estimated = estimated_tokens
            return True

    async def record_success(self, actual_tokens: int) -> None:
        """记录成功调用"""
        async with self._lock:
            self.consecutive_failures = 0
            if self.circuit_state == CircuitState.HALF_OPEN:
                self.circuit_state = CircuitState.CLOSED
                logger.info("Circuit breaker CLOSED after successful call")
            
            # 调整实际消耗
            token_diff = actual_tokens - self._last_estimated
            if token_diff > 0:
                self.token_bucket = max(0, self.token_bucket - token_diff)

    async def record_failure(self, error: Exception) -> None:
        """记录失败调用"""
        async with self._lock:
            self.consecutive_failures += 1
            self.last_failure_time = datetime.utcnow()

            if self.consecutive_failures >= self.config.circuit_failure_threshold:
                self.circuit_state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker OPEN after {self.consecutive_failures} failures"
                )

    def _should_try_recovery(self) -> bool:
        """是否应该尝试恢复"""
        if self.last_failure_time is None:
            return True
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.config.circuit_recovery_timeout

    @property
    def is_healthy(self) -> bool:
        """是否健康"""
        return self.circuit_state != CircuitState.OPEN

    @property
    def available_tokens(self) -> int:
        """可用 token 数量"""
        return int(self.token_bucket)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "circuit_state": self.circuit_state.value,
            "consecutive_failures": self.consecutive_failures,
            "available_tokens": int(self.token_bucket),
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
        }

