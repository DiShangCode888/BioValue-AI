# 外部 API 基类
"""
外部 API 客户端基类
"""

from abc import ABC, abstractmethod
from typing import Any

import aiohttp
from pydantic import BaseModel

from src.utils import get_logger

logger = get_logger(__name__)


class APIResponse(BaseModel):
    """API 响应"""
    success: bool
    data: Any = None
    error: str | None = None
    status_code: int = 0


class ExternalAPIClient(ABC):
    """外部 API 客户端基类"""
    
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取 HTTP 会话"""
        if self._session is None or self._session.closed:
            headers = self._get_headers()
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
        return self._session
    
    def _get_headers(self) -> dict[str, str]:
        """获取请求头"""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    async def close(self):
        """关闭会话"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None
    ) -> APIResponse:
        """GET 请求"""
        session = await self._get_session()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            async with session.get(url, params=params) as response:
                data = await response.json()
                return APIResponse(
                    success=response.status == 200,
                    data=data,
                    status_code=response.status,
                )
        except aiohttp.ClientError as e:
            logger.error(f"API GET error: {e}")
            return APIResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return APIResponse(success=False, error=str(e))
    
    async def post(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None
    ) -> APIResponse:
        """POST 请求"""
        session = await self._get_session()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            async with session.post(url, json=data, params=params) as response:
                resp_data = await response.json()
                return APIResponse(
                    success=response.status in (200, 201),
                    data=resp_data,
                    status_code=response.status,
                )
        except aiohttp.ClientError as e:
            logger.error(f"API POST error: {e}")
            return APIResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return APIResponse(success=False, error=str(e))
    
    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        ...

