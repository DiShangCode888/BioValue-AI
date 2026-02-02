# LLM 抽象层模块
"""
解耦设计的 LLM 抽象层，支持多种提供商切换:
- OpenAI
- DeepSeek
- 通义千问 (Qwen)
- Ollama (本地模型)
"""

from .base import BaseLLM, LLMType
from .factory import LLMFactory, get_llm

__all__ = ["BaseLLM", "LLMType", "LLMFactory", "get_llm"]

