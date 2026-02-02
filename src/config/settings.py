# BioValue-AI 配置管理
"""
统一配置管理模块，支持:
- YAML 配置文件
- 环境变量覆盖
- 多环境配置
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


def load_yaml_config(config_path: str | Path) -> dict[str, Any]:
    """加载 YAML 配置文件，支持环境变量替换"""
    config_path = Path(config_path)
    if not config_path.exists():
        return {}
    
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 替换环境变量 ${VAR_NAME}
    import re
    def replace_env_var(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))
    
    content = re.sub(r'\$\{(\w+)\}', replace_env_var, content)
    return yaml.safe_load(content) or {}


class LLMConfig(BaseSettings):
    """LLM 模型配置"""
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    max_retries: int = 3


class Neo4jConfig(BaseSettings):
    """Neo4j 数据库配置"""
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = ""
    database: str = "biovalue"


class RedisConfig(BaseSettings):
    """Redis 缓存配置"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""


class VectorDBConfig(BaseSettings):
    """向量数据库配置"""
    type: Literal["chroma", "milvus"] = "chroma"
    persist_directory: str = "./data/chroma"
    collection_name: str = "biovalue_docs"


class APIConfig(BaseSettings):
    """API 服务配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]


class CrawlerConfig(BaseSettings):
    """爬虫配置"""
    max_concurrent: int = 5
    request_delay: float = 1.0
    user_agent: str = "BioValue-AI/1.0"


class ParserConfig(BaseSettings):
    """文档解析配置"""
    supported_formats: list[str] = [".pdf", ".docx", ".txt"]
    max_file_size: int = 52428800  # 50MB


class IngestionConfig(BaseSettings):
    """数据摄入配置"""
    clinical_trials_api: str = "https://clinicaltrials.gov/api/v2"
    crawler: CrawlerConfig = Field(default_factory=CrawlerConfig)
    parser: ParserConfig = Field(default_factory=ParserConfig)


class WorkflowConfig(BaseSettings):
    """LangGraph 工作流配置"""
    max_iterations: int = 10
    recursion_limit: int = 50
    checkpoint_enabled: bool = True


class Settings(BaseSettings):
    """全局配置"""
    
    # LLM 模型配置
    reasoning_model: LLMConfig = Field(default_factory=LLMConfig)
    basic_model: LLMConfig = Field(default_factory=LLMConfig)
    extraction_model: LLMConfig = Field(default_factory=LLMConfig)
    embedding_model: LLMConfig = Field(default_factory=LLMConfig)
    
    # 数据库配置
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    vector_db: VectorDBConfig = Field(default_factory=VectorDBConfig)
    
    # 服务配置
    api: APIConfig = Field(default_factory=APIConfig)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    
    # 日志级别
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @classmethod
    def from_yaml(cls, config_path: str | Path) -> "Settings":
        """从 YAML 配置文件加载设置"""
        config = load_yaml_config(config_path)
        
        # 构建设置对象
        settings_dict = {}
        
        # LLM 配置映射
        llm_mapping = {
            "REASONING_MODEL": "reasoning_model",
            "BASIC_MODEL": "basic_model",
            "EXTRACTION_MODEL": "extraction_model",
            "EMBEDDING_MODEL": "embedding_model",
        }
        
        for yaml_key, settings_key in llm_mapping.items():
            if yaml_key in config:
                settings_dict[settings_key] = LLMConfig(**config[yaml_key])
        
        # 其他配置
        if "NEO4J" in config:
            settings_dict["neo4j"] = Neo4jConfig(**config["NEO4J"])
        if "REDIS" in config:
            settings_dict["redis"] = RedisConfig(**config["REDIS"])
        if "VECTOR_DB" in config:
            settings_dict["vector_db"] = VectorDBConfig(**config["VECTOR_DB"])
        if "API" in config:
            settings_dict["api"] = APIConfig(**config["API"])
        if "WORKFLOW" in config:
            settings_dict["workflow"] = WorkflowConfig(**config["WORKFLOW"])
        if "INGESTION" in config:
            ing_config = config["INGESTION"]
            settings_dict["ingestion"] = IngestionConfig(
                clinical_trials_api=ing_config.get("clinical_trials_api", ""),
                crawler=CrawlerConfig(**ing_config.get("crawler", {})),
                parser=ParserConfig(**ing_config.get("parser", {})),
            )
        
        return cls(**settings_dict)


@lru_cache()
def get_settings() -> Settings:
    """获取全局配置单例"""
    config_path = Path(__file__).parent.parent.parent / "conf.yaml"
    if config_path.exists():
        return Settings.from_yaml(config_path)
    return Settings()

