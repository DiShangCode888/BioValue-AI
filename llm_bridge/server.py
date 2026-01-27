"""
LLM Bridge gRPC Server
提供 LLM 推理服务的 gRPC 接口
"""
import asyncio
import logging
import os
import signal
import sys
from concurrent import futures
from datetime import datetime
from typing import Optional

import grpc
import yaml
from grpc_reflection.v1alpha import reflection

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_bridge.llm_provider import LLMProvider
from llm_bridge.mcp_client import MCPClientManager
from llm_bridge.rate_limiter import AdaptiveRateLimiter, RateLimitConfig

# 生成的 proto 文件
# from proto import llm_bridge_pb2, llm_bridge_pb2_grpc

logger = logging.getLogger(__name__)


class LLMBridgeServicer:
    """LLM Bridge gRPC 服务实现"""

    def __init__(self, config: dict):
        self.config = config
        self.llm_provider = LLMProvider(config.get("llm", {}))
        self.mcp_manager: Optional[MCPClientManager] = None
        self.rate_limiter = AdaptiveRateLimiter(
            RateLimitConfig(
                requests_per_minute=config.get("llm", {}).get("rate_limit", {}).get("requests_per_minute", 60),
                tokens_per_minute=config.get("llm", {}).get("rate_limit", {}).get("tokens_per_minute", 100000),
            )
        )
        self.start_time = datetime.utcnow()

    async def initialize(self):
        """初始化服务"""
        # 初始化 MCP 客户端
        if self.config.get("mcp"):
            self.mcp_manager = MCPClientManager(self.config.get("mcp", {}))
            await self.mcp_manager.discover_and_connect()

    async def Infer(self, request, context):
        """单次推理"""
        try:
            # 估算 token 数量
            estimated_tokens = len(request.user_prompt.split()) * 2

            # 获取限速许可
            await self.rate_limiter.acquire(estimated_tokens)

            # 构建消息
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            
            # 添加上下文
            if request.context:
                context_content = "\n\n".join([
                    f"[来源: {ctx.source}]\n{ctx.content}" 
                    for ctx in request.context
                ])
                messages.append({"role": "user", "content": f"相关上下文:\n{context_content}"})
            
            messages.append({"role": "user", "content": request.user_prompt})

            # 处理图片
            image_contents = []
            if request.image_paths:
                for path in request.image_paths:
                    image_contents.append(self._load_image(path))

            # 调用 LLM
            result = await self.llm_provider.infer(
                messages=messages,
                images=image_contents if image_contents else None,
                temperature=request.config.temperature if request.config else 0.7,
                max_tokens=request.config.max_tokens if request.config else 4096,
                tools=self._convert_tools(request.config.tools) if request.config and request.config.enable_tools else None,
            )

            # 记录成功
            await self.rate_limiter.record_success(result.get("usage", {}).get("total_tokens", estimated_tokens))

            # 构建响应
            response = self._build_response(request.trace_id, result)
            return response

        except Exception as e:
            logger.error(f"Infer failed: {e}", exc_info=True)
            await self.rate_limiter.record_failure(e)
            raise

    async def InferStream(self, request, context):
        """流式推理"""
        try:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.user_prompt})

            async for chunk in self.llm_provider.infer_stream(
                messages=messages,
                temperature=request.config.temperature if request.config else 0.7,
                max_tokens=request.config.max_tokens if request.config else 4096,
            ):
                yield self._build_chunk_response(request.trace_id, chunk)

        except Exception as e:
            logger.error(f"InferStream failed: {e}", exc_info=True)
            raise

    async def InferBatch(self, request, context):
        """批量推理"""
        start_time = datetime.utcnow()
        responses = []

        # 并发处理请求
        tasks = [self.Infer(req, context) for req in request.requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                responses.append(self._build_error_response(str(result)))
            else:
                responses.append(result)

        return {
            "responses": responses,
            "total_duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
        }

    async def HealthCheck(self, request, context):
        """健康检查"""
        dependencies = {
            "llm": await self.llm_provider.health_check(),
        }
        
        if self.mcp_manager:
            mcp_health = await self.mcp_manager.health_check()
            for server_id, healthy in mcp_health.items():
                dependencies[f"mcp_{server_id}"] = healthy

        return {
            "healthy": all(dependencies.values()),
            "version": "1.0.0",
            "dependencies": dependencies,
            "uptime_seconds": int((datetime.utcnow() - self.start_time).total_seconds()),
        }

    def _load_image(self, path: str) -> bytes:
        """加载图片"""
        with open(path, "rb") as f:
            return f.read()

    def _convert_tools(self, tools) -> list:
        """转换工具定义"""
        if not tools:
            return None
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema,
            }
            for t in tools
        ]

    def _build_response(self, trace_id: str, result: dict):
        """构建响应"""
        return {
            "trace_id": trace_id,
            "status": "SUCCESS",
            "thought": {
                "reasoning": result.get("reasoning", ""),
                "plan": result.get("plan", ""),
                "confidence": result.get("confidence", 0.8),
            },
            "tool_call": result.get("tool_call"),
            "final_answer": result.get("content", ""),
            "usage": result.get("usage", {}),
        }

    def _build_chunk_response(self, trace_id: str, chunk: dict):
        """构建流式响应块"""
        return {
            "trace_id": trace_id,
            "type": chunk.get("type", "ANSWER"),
            "content": chunk.get("content", ""),
            "is_final": chunk.get("is_final", False),
        }

    def _build_error_response(self, error_message: str):
        """构建错误响应"""
        return {
            "status": "ERROR",
            "error_message": error_message,
        }


async def serve(config: dict):
    """启动 gRPC 服务"""
    server = grpc.aio.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ("grpc.max_receive_message_length", 50 * 1024 * 1024),  # 50MB
            ("grpc.max_send_message_length", 50 * 1024 * 1024),
        ],
    )

    # 创建服务实例
    servicer = LLMBridgeServicer(config)
    await servicer.initialize()

    # 注册服务 (需要生成的 proto 代码)
    # llm_bridge_pb2_grpc.add_LLMBridgeServicer_to_server(servicer, server)

    # 启用反射 (用于调试)
    # SERVICE_NAMES = (
    #     llm_bridge_pb2.DESCRIPTOR.services_by_name['LLMBridge'].full_name,
    #     reflection.SERVICE_NAME,
    # )
    # reflection.enable_server_reflection(SERVICE_NAMES, server)

    port = config.get("server", {}).get("port", 50051)
    server.add_insecure_port(f"[::]:{port}")

    logger.info(f"Starting LLM Bridge server on port {port}")
    await server.start()

    # 优雅关闭
    async def shutdown():
        logger.info("Shutting down server...")
        await server.stop(5)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))

    await server.wait_for_termination()


def load_config(config_path: str = None) -> dict:
    """加载配置文件"""
    if config_path is None:
        config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")

    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main():
    """主入口"""
    import argparse

    parser = argparse.ArgumentParser(description="LLM Bridge Server")
    parser.add_argument("--config", type=str, help="配置文件路径")
    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # 加载配置
    config = load_config(args.config)

    # 启动服务
    asyncio.run(serve(config))


if __name__ == "__main__":
    main()

