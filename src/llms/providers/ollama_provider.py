# Ollama 本地 LLM 提供商实现
"""
Ollama 本地部署的 LLM 实现，支持:
- llama3
- qwen2
- deepseek-coder
- 等所有 Ollama 支持的模型
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


class OllamaLLM(BaseLLM):
    """Ollama 本地 LLM 实现"""
    
    def __init__(
        self,
        model: str = "llama3",
        api_key: str = "",  # Ollama 不需要 API key
        base_url: str = "http://localhost:11434",
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
                headers={"Content-Type": "application/json"},
                timeout=120.0,  # 本地模型可能需要更长时间
            )
        return self._client
    
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
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            response = await self.client.post(
                "/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "options": {
                        "temperature": kwargs.get("temperature", self.temperature),
                        "num_predict": kwargs.get("max_tokens", self.max_tokens),
                    },
                    "stream": False,
                },
            )
            
            response.raise_for_status()
            data = response.json()
            
            return LLMResponse(
                content=data["response"],
                model=self.model,
                usage={
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                },
                raw_response=data,
            )
            
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Ollama: {e}. Is Ollama running?")
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
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            async with self.client.stream(
                "POST",
                "/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "options": {
                        "temperature": kwargs.get("temperature", self.temperature),
                        "num_predict": kwargs.get("max_tokens", self.max_tokens),
                    },
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    try:
                        data = json.loads(line)
                        if content := data.get("response"):
                            yield content
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
                            
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Ollama: {e}")
    
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

只输出 JSON，不要输出其他内容。

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
            embeddings = []
            for t in text:
                response = await self.client.post(
                    "/api/embeddings",
                    json={
                        "model": self.model,
                        "prompt": t,
                    },
                )
                response.raise_for_status()
                data = response.json()
                embeddings.append(data["embedding"])
            
            return embeddings
            
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Ollama: {e}")
    
    async def close(self):
        """关闭客户端连接"""
        if self._client:
            await self._client.aclose()
            self._client = None

