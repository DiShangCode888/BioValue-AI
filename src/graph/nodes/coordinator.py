# 协调器节点
"""
协调器 Agent: 负责理解用户意图，分配任务到合适的处理节点
"""

from langchain_core.messages import AIMessage, HumanMessage

from src.llms import get_llm
from src.utils import get_logger

from ..state import (
    CoordinatorDecision,
    Task,
    TaskStatus,
    TaskType,
    WorkflowState,
)

logger = get_logger(__name__)

COORDINATOR_SYSTEM_PROMPT = """你是 BioValue-AI 创新药知识图谱系统的协调器 Agent。

你的职责是:
1. 理解用户的查询意图
2. 分解复杂任务为可执行的子任务
3. 决定下一步应该调用哪个专门的 Agent

可用的 Agent 包括:
- extract: 数据提取 Agent - 从文档、URL或API提取结构化数据
- build_graph: 图谱构建 Agent - 将提取的数据构建到知识图谱中
- analyze: 分析 Agent - 执行竞争分析、机会挖掘、数据诚信检查等
- report: 报告 Agent - 生成分析报告和总结
- query: 查询 Agent - 执行知识图谱查询
- end: 结束工作流

任务类型说明:
- extract_data: 用户提供了需要提取数据的来源（PDF、URL等）
- build_graph: 需要将数据写入知识图谱
- analyze_competition: 竞争坍缩分析、竞品对比
- find_opportunity: 空白点挖掘、投资机会发现
- check_integrity: 数据诚信检查、可疑数据识别
- generate_report: 生成综合报告
- query_graph: 查询知识图谱中的信息

请根据用户查询和当前状态，做出下一步决策。
"""


async def coordinator_node(state: WorkflowState) -> dict:
    """协调器节点
    
    分析用户意图，决定下一步行动。
    """
    logger.info("Coordinator node processing...")
    
    # 检查迭代次数
    if state.iteration_count >= state.max_iterations:
        logger.warning("Max iterations reached, ending workflow")
        return {
            "next_node": "reporter",
            "should_continue": False,
        }
    
    # 获取最新的用户消息
    user_message = ""
    for msg in reversed(state.messages):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break
    
    if not user_message and state.user_query:
        user_message = state.user_query
    
    # 构建上下文
    context = f"""
当前用户查询: {user_message}

已完成任务: {len(state.completed_tasks)}
待处理任务: {len(state.task_queue)}
已提取实体: {len(state.extracted_entities)}
分析结果数: {len(state.analysis_results)}

迭代次数: {state.iteration_count}
"""
    
    # 使用 LLM 做决策
    llm = get_llm("basic")
    
    try:
        decision = await llm.structured_output(
            prompt=f"请分析以下情况并决定下一步行动:\n{context}",
            schema=CoordinatorDecision,
            system_prompt=COORDINATOR_SYSTEM_PROMPT,
        )
        
        logger.info(f"Coordinator decision: {decision.next_action} - {decision.reasoning}")
        
        # 创建任务
        task = None
        next_node = "end"
        
        if decision.next_action == "extract":
            task = Task(
                id=f"task_{state.iteration_count}_extract",
                type=TaskType.EXTRACT_DATA,
                description="从数据源提取结构化信息",
                parameters=decision.task_params,
            )
            next_node = "extractor"
            
        elif decision.next_action == "build_graph":
            task = Task(
                id=f"task_{state.iteration_count}_build",
                type=TaskType.BUILD_GRAPH,
                description="构建知识图谱",
                parameters=decision.task_params,
            )
            next_node = "graph_builder"
            
        elif decision.next_action == "analyze":
            # 确定具体分析类型
            analysis_type = decision.task_params.get("analysis_type", "competition")
            task_type_map = {
                "competition": TaskType.ANALYZE_COMPETITION,
                "opportunity": TaskType.FIND_OPPORTUNITY,
                "integrity": TaskType.CHECK_INTEGRITY,
            }
            task = Task(
                id=f"task_{state.iteration_count}_analyze",
                type=task_type_map.get(analysis_type, TaskType.ANALYZE_COMPETITION),
                description=f"执行 {analysis_type} 分析",
                parameters=decision.task_params,
            )
            next_node = "analyzer"
            
        elif decision.next_action == "report":
            task = Task(
                id=f"task_{state.iteration_count}_report",
                type=TaskType.GENERATE_REPORT,
                description="生成分析报告",
                parameters=decision.task_params,
            )
            next_node = "reporter"
            
        elif decision.next_action == "query":
            task = Task(
                id=f"task_{state.iteration_count}_query",
                type=TaskType.QUERY_GRAPH,
                description="查询知识图谱",
                parameters=decision.task_params,
            )
            next_node = "analyzer"
            
        else:  # end
            next_node = "reporter"
        
        # 更新状态
        updates = {
            "next_node": next_node,
            "iteration_count": state.iteration_count + 1,
            "user_query": user_message if not state.user_query else state.user_query,
        }
        
        if task:
            updates["current_task"] = task
        
        # 添加 AI 消息记录决策
        ai_message = AIMessage(
            content=f"[协调器决策] {decision.reasoning}\n下一步: {decision.next_action}"
        )
        updates["messages"] = [ai_message]
        
        return updates
        
    except Exception as e:
        logger.error(f"Coordinator error: {e}")
        return {
            "next_node": "reporter",
            "should_continue": False,
            "messages": [AIMessage(content=f"协调器处理出错: {str(e)}")],
        }

