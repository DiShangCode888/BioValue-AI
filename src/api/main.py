# FastAPI 应用入口
"""
BioValue-AI REST API 服务
"""

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.knowledge import get_neo4j_client, init_neo4j_schema
from src.utils import get_logger, setup_logging

from .routes import graph, data, analysis, workflow

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("Starting BioValue-AI API...")
    settings = get_settings()
    setup_logging(settings.log_level)
    
    # 初始化 Neo4j
    try:
        client = get_neo4j_client()
        await client.connect()
        await init_neo4j_schema(client)
        logger.info("Neo4j initialized")
    except Exception as e:
        logger.warning(f"Neo4j initialization failed: {e}")
    
    yield
    
    # 关闭
    logger.info("Shutting down BioValue-AI API...")
    try:
        client = get_neo4j_client()
        await client.close()
    except Exception:
        pass


# 创建 FastAPI 应用
app = FastAPI(
    title="BioValue-AI API",
    description="创新药全要素知识图谱智能投资分析平台 API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 配置 CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(graph.router, prefix="/api/v1/graph", tags=["Graph"])
app.include_router(data.router, prefix="/api/v1/data", tags=["Data"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["Analysis"])
app.include_router(workflow.router, prefix="/api/v1/workflow", tags=["Workflow"])


@app.get("/")
async def root():
    """API 根路由"""
    return {
        "name": "BioValue-AI API",
        "version": "0.1.0",
        "description": "创新药全要素知识图谱智能投资分析平台",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    health = {
        "status": "healthy",
        "services": {}
    }
    
    # 检查 Neo4j
    try:
        client = get_neo4j_client()
        await client.connect()
        stats = await client.get_statistics()
        health["services"]["neo4j"] = {
            "status": "connected",
            "nodes": sum(stats.get("nodes", {}).values()),
            "edges": sum(stats.get("edges", {}).values()),
        }
    except Exception as e:
        health["services"]["neo4j"] = {
            "status": "error",
            "error": str(e),
        }
        health["status"] = "degraded"
    
    return health


def run():
    """启动 API 服务"""
    settings = get_settings()
    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.debug,
    )


if __name__ == "__main__":
    run()

