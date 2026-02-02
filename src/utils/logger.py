# 日志配置模块
"""
基于 structlog 的结构化日志系统
"""

import logging
import sys
from typing import Any

import structlog

_configured = False


def setup_logging(log_level: str = "INFO") -> None:
    """配置结构化日志"""
    global _configured
    if _configured:
        return
    
    # 配置标准日志
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # 配置 structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    _configured = True


def get_logger(name: str = __name__) -> Any:
    """获取日志记录器"""
    setup_logging()
    return structlog.get_logger(name)

