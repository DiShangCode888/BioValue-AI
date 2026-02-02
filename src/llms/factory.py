# LLM 工厂模块
"""
LLM 工厂模式实现，支持:
- 根据配置动态创建 LLM 实例
- 缓存 LLM 实例避免重复创建
- 统一的 LLM 获取接口
"""

from functools import lru_cache
from typing import Any

from src.config import get_settings, LLMConfig
from src.utils import get_logger

from .base import BaseLLM, LLMType
from .providers import DeepSeekLLM, OllamaLLM, OpenAILLM, QwenLLM

logger = get_logger(__name__)

# LLM 实例缓存
_llm_cache: dict[LLMType, BaseLLM] = {}


class LLMFactory:
    """LLM 工厂类
    
    负责根据配置创建不同类型的 LLM 实例。
    使用工厂模式实现 LLM 提供商的解耦。
    """
    
    # 提供商映射
    PROVIDER_MAP = {
        "openai": OpenAILLM,
        "deepseek": DeepSeekLLM,
        "qwen": QwenLLM,
        "dashscope": QwenLLM,
        "ollama": OllamaLLM,
    }
    
    @classmethod
    def detect_provider(cls, config: LLMConfig) -> str:
        """根据配置检测 LLM 提供商"""
        base_url = config.base_url.lower()
        
        if "deepseek" in base_url:
            return "deepseek"
        elif "dashscope" in base_url or "aliyun" in base_url:
            return "qwen"
        elif "localhost" in base_url or "127.0.0.1" in base_url:
            # 检查是否是 Ollama
            if "11434" in base_url:
                return "ollama"
            return "openai"  # 默认兼容 OpenAI API
        elif "openai" in base_url:
            return "openai"
        else:
            # 默认使用 OpenAI 兼容接口
            return "openai"
    
    @classmethod
    def create(
        cls,
        config: LLMConfig,
        provider: str | None = None,
    ) -> BaseLLM:
        """创建 LLM 实例
        
        Args:
            config: LLM 配置
            provider: 指定提供商，如果为 None 则自动检测
            
        Returns:
            BaseLLM: LLM 实例
        """
        if provider is None:
            provider = cls.detect_provider(config)
        
        llm_class = cls.PROVIDER_MAP.get(provider)
        if llm_class is None:
            logger.warning(f"Unknown provider: {provider}, fallback to OpenAI")
            llm_class = OpenAILLM
        
        logger.info(f"Creating LLM instance: {llm_class.__name__} with model {config.model}")
        
        return llm_class(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
    
    @classmethod
    def create_from_settings(cls, llm_type: LLMType) -> BaseLLM:
        """从全局设置创建 LLM 实例
        
        Args:
            llm_type: LLM 类型 (reasoning/basic/extraction/embedding)
            
        Returns:
            BaseLLM: LLM 实例
        """
        settings = get_settings()
        
        config_map = {
            "reasoning": settings.reasoning_model,
            "basic": settings.basic_model,
            "extraction": settings.extraction_model,
            "embedding": settings.embedding_model,
        }
        
        config = config_map.get(llm_type)
        if config is None:
            raise ValueError(f"Unknown LLM type: {llm_type}")
        
        return cls.create(config)


def get_llm(llm_type: LLMType = "basic") -> BaseLLM:
    """获取 LLM 实例
    
    使用缓存机制，避免重复创建实例。
    
    Args:
        llm_type: LLM 类型
        
    Returns:
        BaseLLM: LLM 实例
    """
    if llm_type not in _llm_cache:
        _llm_cache[llm_type] = LLMFactory.create_from_settings(llm_type)
    
    return _llm_cache[llm_type]


def clear_llm_cache():
    """清除 LLM 缓存"""
    _llm_cache.clear()


# 便捷函数
def get_reasoning_llm() -> BaseLLM:
    """获取推理 LLM"""
    return get_llm("reasoning")


def get_basic_llm() -> BaseLLM:
    """获取基础 LLM"""
    return get_llm("basic")


def get_extraction_llm() -> BaseLLM:
    """获取提取 LLM"""
    return get_llm("extraction")


def get_embedding_llm() -> BaseLLM:
    """获取嵌入 LLM"""
    return get_llm("embedding")

