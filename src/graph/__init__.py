# LangGraph 工作流模块
"""
基于 LangGraph 的多 Agent 工作流系统:
- Coordinator: 协调器，分发任务
- Extractor: 数据提取 Agent
- GraphBuilder: 图谱构建 Agent
- Analyzer: 分析推理 Agent
- Reporter: 报告生成 Agent
"""

from .builder import build_graph, build_graph_with_memory
from .state import WorkflowState

__all__ = ["build_graph", "build_graph_with_memory", "WorkflowState"]

