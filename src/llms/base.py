# LLM 基类接口定义
"""
定义 LLM 的统一抽象接口，实现解耦设计
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Literal, TypeVar

from pydantic import BaseModel

# LLM 类型定义
LLMType = Literal["reasoning", "basic", "extraction", "embedding"]

# 泛型类型变量，用于结构化输出
T = TypeVar("T", bound=BaseModel)


class LLMResponse(BaseModel):
    """LLM 响应模型"""
    content: str
    model: str
    usage: dict[str, int] | None = None
    raw_response: Any = None


class BaseLLM(ABC):
    """LLM 抽象基类
    
    所有 LLM 提供商实现必须继承此基类，实现统一接口。
    这是解耦设计的核心，允许运行时切换不同的 LLM 提供商。
    """
    
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_kwargs = kwargs
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs
    ) -> LLMResponse:
        """生成文本响应
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            **kwargs: 额外参数
            
        Returns:
            LLMResponse: 包含生成内容的响应对象
        """
        ...
    
    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """流式生成文本
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            **kwargs: 额外参数
            
        Yields:
            str: 生成的文本片段
        """
        ...
    
    @abstractmethod
    async def structured_output(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str | None = None,
        **kwargs
    ) -> T:
        """生成结构化输出
        
        使用 Pydantic 模型约束输出格式，适用于数据提取场景。
        
        Args:
            prompt: 用户提示词
            schema: Pydantic 模型类，定义输出结构
            system_prompt: 系统提示词
            **kwargs: 额外参数
            
        Returns:
            T: 符合 schema 定义的结构化对象
        """
        ...
    
    @abstractmethod
    async def embed(self, text: str | list[str]) -> list[list[float]]:
        """生成文本嵌入向量
        
        Args:
            text: 单个文本或文本列表
            
        Returns:
            list[list[float]]: 嵌入向量列表
        """
        ...
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model})"


class LLMError(Exception):
    """LLM 相关错误基类"""
    pass


class LLMConnectionError(LLMError):
    """连接错误"""
    pass


class LLMRateLimitError(LLMError):
    """速率限制错误"""
    pass


class LLMResponseError(LLMError):
    """响应解析错误"""
    pass

