# LangGraph 状态定义
"""
定义工作流状态模型，包括:
- 消息历史
- 当前任务
- 中间结果
- 最终输出
"""

from enum import Enum
from typing import Any, Literal, Optional

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """任务类型枚举"""
    EXTRACT_DATA = "extract_data"          # 从文档/URL提取数据
    BUILD_GRAPH = "build_graph"            # 构建知识图谱
    ANALYZE_COMPETITION = "analyze_competition"  # 竞争分析
    FIND_OPPORTUNITY = "find_opportunity"  # 机会挖掘
    CHECK_INTEGRITY = "check_integrity"    # 数据诚信检查
    GENERATE_REPORT = "generate_report"    # 生成报告
    QUERY_GRAPH = "query_graph"            # 查询图谱
    CHAT = "chat"                          # 普通对话


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    """任务模型"""
    id: str
    type: TaskType
    description: str
    status: TaskStatus = TaskStatus.PENDING
    parameters: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    error: Optional[str] = None


class ExtractedEntity(BaseModel):
    """提取的实体"""
    entity_type: str
    data: dict[str, Any]
    source: str
    confidence: float = 1.0


class AnalysisResult(BaseModel):
    """分析结果"""
    analysis_type: str
    findings: list[dict[str, Any]]
    recommendations: list[str]
    confidence_score: float
    raw_data: Optional[dict] = None


class WorkflowState(MessagesState):
    """工作流状态
    
    继承 MessagesState 以支持消息历史管理，
    并添加创新药知识图谱特有的状态字段。
    """
    
    # 基本信息
    session_id: str = ""
    user_query: str = ""
    locale: str = "zh-CN"
    
    # 任务管理
    current_task: Optional[Task] = None
    task_queue: list[Task] = Field(default_factory=list)
    completed_tasks: list[Task] = Field(default_factory=list)
    
    # 数据提取
    extracted_entities: list[ExtractedEntity] = Field(default_factory=list)
    source_documents: list[str] = Field(default_factory=list)
    
    # 图谱操作
    created_nodes: list[str] = Field(default_factory=list)
    created_edges: list[str] = Field(default_factory=list)
    graph_query_results: list[dict] = Field(default_factory=list)
    
    # 分析结果
    analysis_results: list[AnalysisResult] = Field(default_factory=list)
    
    # 最终输出
    final_report: str = ""
    summary: str = ""
    
    # 控制流
    next_node: Optional[str] = None
    should_continue: bool = True
    iteration_count: int = 0
    max_iterations: int = 10


class CoordinatorDecision(BaseModel):
    """协调器决策"""
    next_action: Literal[
        "extract", "build_graph", "analyze", "report", "query", "end"
    ]
    reasoning: str
    task_params: dict[str, Any] = Field(default_factory=dict)


class ExtractionPlan(BaseModel):
    """数据提取计划"""
    source_type: Literal["document", "url", "api", "manual"]
    target_entities: list[str]
    extraction_strategy: str


class GraphBuildPlan(BaseModel):
    """图谱构建计划"""
    nodes_to_create: list[dict[str, Any]]
    edges_to_create: list[dict[str, Any]]
    validation_rules: list[str]


class AnalysisPlan(BaseModel):
    """分析计划"""
    analysis_type: Literal[
        "competition_collapse",
        "opportunity_discovery",
        "data_integrity",
        "drug_profile",
        "indication_landscape"
    ]
    parameters: dict[str, Any]
    output_format: str = "structured"

