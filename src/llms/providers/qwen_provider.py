# 通义千问 LLM 提供商实现
"""
阿里云通义千问 API 的 LLM 实现，支持:
- qwen-turbo
- qwen-plus
- qwen-max
- text-embedding-v2
"""

import json
from typing import Any, AsyncIterator, TypeVar

import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from ..base import (
    BaseLLM,
    LLMConnectionError,
    LLMRateLimitError,
    LLMResponse,
    LLMResponseError,
)

T = TypeVar("T", bound=BaseModel)


class QwenLLM(BaseLLM):
    """通义千问 LLM 实现"""
    
    def __init__(
        self,
        model: str = "qwen-turbo",
        api_key: str = "",
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ):
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        self._client: httpx.AsyncClient | None = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client
    
    def _build_messages(
        self,
        prompt: str,
        system_prompt: str | None = None
    ) -> list[dict[str, str]]:
        """构建消息列表"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs
    ) -> LLMResponse:
        """生成文本响应"""
        try:
            response = await self.client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": self._build_messages(prompt, system_prompt),
                    "temperature": kwargs.get("temperature", self.temperature),
                    "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                },
            )
            
            if response.status_code == 429:
                raise LLMRateLimitError("Rate limit exceeded")
            
            response.raise_for_status()
            data = response.json()
            
            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model=data["model"],
                usage=data.get("usage"),
                raw_response=data,
            )
            
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Qwen: {e}")
        except httpx.HTTPStatusError as e:
            raise LLMResponseError(f"HTTP error: {e}")
    
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """流式生成文本"""
        try:
            async with self.client.stream(
                "POST",
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": self._build_messages(prompt, system_prompt),
                    "temperature": kwargs.get("temperature", self.temperature),
                    "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            if content := chunk["choices"][0]["delta"].get("content"):
                                yield content
                        except json.JSONDecodeError:
                            continue
                            
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Qwen: {e}")
    
    async def structured_output(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str | None = None,
        **kwargs
    ) -> T:
        """生成结构化输出"""
        schema_json = schema.model_json_schema()
        enhanced_system = f"""你必须以 JSON 格式响应，严格遵循以下 schema:
{json.dumps(schema_json, ensure_ascii=False, indent=2)}

{system_prompt or ''}"""
        
        response = await self.generate(
            prompt=prompt,
            system_prompt=enhanced_system,
            temperature=0,
            **kwargs
        )
        
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content.strip())
            return schema.model_validate(data)
        except (json.JSONDecodeError, ValueError) as e:
            raise LLMResponseError(f"Failed to parse structured output: {e}")
    
    async def embed(self, text: str | list[str]) -> list[list[float]]:
        """生成文本嵌入向量"""
        if isinstance(text, str):
            text = [text]
        
        try:
            response = await self.client.post(
                "/embeddings",
                json={
                    "model": "text-embedding-v2",
                    "input": text,
                },
            )
            response.raise_for_status()
            data = response.json()
            
            return [item["embedding"] for item in data["data"]]
            
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Qwen: {e}")
    
    async def close(self):
        """关闭客户端连接"""
        if self._client:
            await self._client.aclose()
            self._client = None

