# LangGraph 工作流构建器
"""
构建和编译 LangGraph 工作流
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.utils import get_logger

from .state import WorkflowState
from .nodes import (
    coordinator_node,
    extractor_node,
    graph_builder_node,
    analyzer_node,
    reporter_node,
)

logger = get_logger(__name__)


def _route_from_coordinator(state: WorkflowState) -> str:
    """从协调器节点路由到下一个节点"""
    next_node = state.next_node
    
    if not next_node or not state.should_continue:
        return "reporter"
    
    # 映射到实际节点名称
    node_mapping = {
        "extractor": "extractor",
        "extract": "extractor",
        "graph_builder": "graph_builder",
        "build_graph": "graph_builder",
        "analyzer": "analyzer",
        "analyze": "analyzer",
        "query": "analyzer",
        "reporter": "reporter",
        "report": "reporter",
        "end": "reporter",
    }
    
    return node_mapping.get(next_node, "reporter")


def _route_from_node(state: WorkflowState) -> str:
    """从处理节点路由回协调器或结束"""
    if not state.should_continue:
        return "reporter"
    
    return "coordinator"


def _build_base_graph() -> StateGraph:
    """构建基础状态图"""
    builder = StateGraph(WorkflowState)
    
    # 添加节点
    builder.add_node("coordinator", coordinator_node)
    builder.add_node("extractor", extractor_node)
    builder.add_node("graph_builder", graph_builder_node)
    builder.add_node("analyzer", analyzer_node)
    builder.add_node("reporter", reporter_node)
    
    # 添加边
    # 从 START 到协调器
    builder.add_edge(START, "coordinator")
    
    # 从协调器路由到各个处理节点
    builder.add_conditional_edges(
        "coordinator",
        _route_from_coordinator,
        {
            "extractor": "extractor",
            "graph_builder": "graph_builder",
            "analyzer": "analyzer",
            "reporter": "reporter",
        }
    )
    
    # 从各处理节点路由回协调器或报告器
    builder.add_conditional_edges(
        "extractor",
        _route_from_node,
        {
            "coordinator": "coordinator",
            "reporter": "reporter",
        }
    )
    
    builder.add_conditional_edges(
        "graph_builder",
        _route_from_node,
        {
            "coordinator": "coordinator",
            "reporter": "reporter",
        }
    )
    
    builder.add_conditional_edges(
        "analyzer",
        _route_from_node,
        {
            "coordinator": "coordinator",
            "reporter": "reporter",
        }
    )
    
    # 报告器是终点
    builder.add_edge("reporter", END)
    
    return builder


def build_graph():
    """构建并编译工作流图（无状态持久化）"""
    builder = _build_base_graph()
    graph = builder.compile()
    logger.info("Workflow graph built without memory")
    return graph


def build_graph_with_memory():
    """构建并编译工作流图（带状态持久化）"""
    builder = _build_base_graph()
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)
    logger.info("Workflow graph built with memory")
    return graph


# 预编译的图实例
graph = build_graph()


async def run_workflow(
    user_input: str,
    session_id: str = "default",
    max_iterations: int = 10,
) -> dict:
    """运行工作流
    
    Args:
        user_input: 用户输入
        session_id: 会话ID
        max_iterations: 最大迭代次数
        
    Returns:
        dict: 工作流最终状态
    """
    initial_state = {
        "messages": [{"role": "user", "content": user_input}],
        "user_query": user_input,
        "session_id": session_id,
        "max_iterations": max_iterations,
    }
    
    config = {
        "configurable": {
            "thread_id": session_id,
        },
        "recursion_limit": 50,
    }
    
    logger.info(f"Starting workflow with input: {user_input[:100]}...")
    
    final_state = None
    async for state in graph.astream(
        input=initial_state,
        config=config,
        stream_mode="values"
    ):
        final_state = state
        
        # 打印中间状态
        if "messages" in state and state["messages"]:
            last_msg = state["messages"][-1]
            if hasattr(last_msg, "content"):
                logger.debug(f"Workflow message: {last_msg.content[:100]}...")
    
    logger.info("Workflow completed")
    return final_state


async def run_workflow_stream(
    user_input: str,
    session_id: str = "default",
    max_iterations: int = 10,
):
    """流式运行工作流
    
    Args:
        user_input: 用户输入
        session_id: 会话ID
        max_iterations: 最大迭代次数
        
    Yields:
        dict: 工作流中间状态
    """
    initial_state = {
        "messages": [{"role": "user", "content": user_input}],
        "user_query": user_input,
        "session_id": session_id,
        "max_iterations": max_iterations,
    }
    
    config = {
        "configurable": {
            "thread_id": session_id,
        },
        "recursion_limit": 50,
    }
    
    async for state in graph.astream(
        input=initial_state,
        config=config,
        stream_mode="values"
    ):
        yield state

