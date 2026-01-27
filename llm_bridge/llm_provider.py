"""
LLM Provider
支持多种 LLM 提供商的统一接口
"""
import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """LLM 提供商基类"""

    @abstractmethod
    async def infer(
        self,
        messages: List[Dict[str, str]],
        images: Optional[List[bytes]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """执行推理"""
        pass

    @abstractmethod
    async def infer_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式推理"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI 提供商"""

    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.model = config.get("model", "gpt-4-turbo")
        self.timeout = config.get("timeout", 120)

    async def infer(
        self,
        messages: List[Dict[str, str]],
        images: Optional[List[bytes]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """执行推理"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 处理多模态输入
        processed_messages = self._process_messages(messages, images)

        payload = {
            "model": self.model,
            "messages": processed_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = self._format_tools(tools)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenAI API error: {response.status} - {error_text}")

                result = await response.json()

                choice = result["choices"][0]
                message = choice["message"]

                return {
                    "content": message.get("content", ""),
                    "tool_call": self._parse_tool_call(message.get("tool_calls")),
                    "usage": {
                        "prompt_tokens": result["usage"]["prompt_tokens"],
                        "completion_tokens": result["usage"]["completion_tokens"],
                        "total_tokens": result["usage"]["total_tokens"],
                    },
                    "model": result["model"],
                }

    async def infer_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式推理"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as response:
                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            yield {"type": "ANSWER", "content": "", "is_final": True}
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0]["delta"]
                            if "content" in delta:
                                yield {
                                    "type": "ANSWER",
                                    "content": delta["content"],
                                    "is_final": False,
                                }
                        except json.JSONDecodeError:
                            continue

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/models",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def _process_messages(
        self, messages: List[Dict[str, str]], images: Optional[List[bytes]]
    ) -> List[Dict]:
        """处理消息，支持多模态"""
        if not images:
            return messages

        processed = []
        for msg in messages:
            if msg["role"] == "user" and images:
                content = [{"type": "text", "text": msg["content"]}]
                for img in images:
                    import base64
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64.b64encode(img).decode()}"
                        },
                    })
                processed.append({"role": "user", "content": content})
            else:
                processed.append(msg)

        return processed

    def _format_tools(self, tools: List[Dict]) -> List[Dict]:
        """格式化工具定义"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": json.loads(t["parameters"]) if isinstance(t["parameters"], str) else t["parameters"],
                },
            }
            for t in tools
        ]

    def _parse_tool_call(self, tool_calls: Optional[List]) -> Optional[Dict]:
        """解析工具调用"""
        if not tool_calls:
            return None

        tc = tool_calls[0]
        return {
            "tool_name": tc["function"]["name"],
            "tool_input": tc["function"]["arguments"],
        }


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek 提供商"""

    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get("api_key") or os.environ.get("DEEPSEEK_API_KEY")
        self.base_url = config.get("base_url", "https://api.deepseek.com/v1")
        self.model = config.get("model", "deepseek-chat")
        self.timeout = config.get("timeout", 120)

    async def infer(
        self,
        messages: List[Dict[str, str]],
        images: Optional[List[bytes]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """执行推理"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"DeepSeek API error: {response.status} - {error_text}")

                result = await response.json()
                choice = result["choices"][0]
                message = choice["message"]

                return {
                    "content": message.get("content", ""),
                    "usage": result.get("usage", {}),
                    "model": result["model"],
                }

    async def infer_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式推理"""
        # 与 OpenAI 类似的实现
        pass

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/models",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    return response.status == 200
        except Exception:
            return False


class LLMProvider:
    """LLM 提供商管理器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.primary = self._create_provider(config)
        self.fallback = None

        # 创建降级提供商
        fallback_config = config.get("fallback", {})
        if fallback_config.get("enabled"):
            self.fallback = self._create_provider(fallback_config)

    def _create_provider(self, config: Dict[str, Any]) -> BaseLLMProvider:
        """创建提供商实例"""
        provider_type = config.get("provider", "openai").lower()

        if provider_type == "openai":
            return OpenAIProvider(config)
        elif provider_type == "deepseek":
            return DeepSeekProvider(config)
        else:
            raise ValueError(f"Unknown provider: {provider_type}")

    async def infer(
        self,
        messages: List[Dict[str, str]],
        images: Optional[List[bytes]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """执行推理，支持降级"""
        try:
            return await self.primary.infer(
                messages, images, temperature, max_tokens, tools
            )
        except Exception as e:
            logger.error(f"Primary LLM failed: {e}")
            if self.fallback:
                logger.info("Falling back to secondary provider")
                return await self.fallback.infer(
                    messages, images, temperature, max_tokens, tools
                )
            raise

    async def infer_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式推理"""
        async for chunk in self.primary.infer_stream(messages, temperature, max_tokens):
            yield chunk

    async def health_check(self) -> bool:
        """健康检查"""
        return await self.primary.health_check()

