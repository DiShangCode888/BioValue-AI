# 报告生成节点
"""
报告生成 Agent: 汇总分析结果，生成最终报告
"""

from langchain_core.messages import AIMessage

from src.llms import get_llm
from src.utils import get_logger

from ..state import (
    Task,
    TaskStatus,
    WorkflowState,
)

logger = get_logger(__name__)

REPORTER_SYSTEM_PROMPT = """你是 BioValue-AI 的报告生成专家 Agent。

你的职责是将分析结果汇总成结构化的投资分析报告。

报告应包括:
1. **执行摘要**: 关键发现和结论
2. **分析详情**: 各项分析的详细结果
3. **数据支撑**: 引用的知识图谱数据
4. **投资建议**: 基于分析的具体建议
5. **风险提示**: 潜在风险和不确定性

报告应当:
- 专业、客观
- 数据驱动
- 逻辑清晰
- 可操作性强
"""


async def reporter_node(state: WorkflowState) -> dict:
    """报告生成节点"""
    logger.info("Reporter node processing...")
    
    # 汇总所有分析结果
    analysis_results = state.analysis_results
    completed_tasks = state.completed_tasks
    extracted_entities = state.extracted_entities
    created_nodes = state.created_nodes
    graph_query_results = state.graph_query_results
    
    # 构建报告上下文
    context = f"""
# 工作流执行摘要

## 用户查询
{state.user_query}

## 完成的任务
共完成 {len(completed_tasks)} 个任务:
"""
    
    for task in completed_tasks:
        context += f"- {task.type.value}: {task.description} ({task.status.value})\n"
    
    context += f"""
## 数据提取
提取了 {len(extracted_entities)} 个实体:
"""
    
    entity_types = {}
    for entity in extracted_entities:
        entity_types[entity.entity_type] = entity_types.get(entity.entity_type, 0) + 1
    
    for entity_type, count in entity_types.items():
        context += f"- {entity_type}: {count} 个\n"
    
    context += f"""
## 图谱操作
创建了 {len(created_nodes)} 个节点

## 分析结果
完成 {len(analysis_results)} 项分析:
"""
    
    for result in analysis_results:
        context += f"\n### {result.analysis_type}\n"
        context += f"置信度: {result.confidence_score:.2f}\n"
        if result.findings:
            for finding in result.findings:
                if "llm_analysis" in finding:
                    context += f"\n分析内容:\n{finding['llm_analysis'][:500]}...\n"
        if result.recommendations:
            context += "\n建议:\n"
            for rec in result.recommendations:
                context += f"- {rec}\n"
    
    if graph_query_results:
        context += f"\n## 图谱查询结果\n共 {len(graph_query_results)} 条结果\n"
    
    # 使用 LLM 生成最终报告
    llm = get_llm("basic")
    
    report_prompt = f"""请基于以下工作流执行结果，生成一份专业的投资分析报告:

{context}

请按照以下结构生成报告:
1. 执行摘要 (100字以内)
2. 关键发现
3. 详细分析
4. 投资建议
5. 风险提示
"""
    
    try:
        response = await llm.generate(
            prompt=report_prompt,
            system_prompt=REPORTER_SYSTEM_PROMPT,
        )
        
        final_report = response.content
        
        # 生成简短摘要
        summary_prompt = f"请用一句话总结以下报告的核心结论:\n\n{final_report[:1000]}"
        summary_response = await llm.generate(prompt=summary_prompt)
        summary = summary_response.content
        
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        final_report = f"报告生成失败: {e}\n\n原始上下文:\n{context}"
        summary = "报告生成过程中出现错误"
    
    # 构建最终消息
    ai_message = AIMessage(
        content=f"[报告生成器] 分析报告已生成\n\n{final_report}"
    )
    
    return {
        "final_report": final_report,
        "summary": summary,
        "should_continue": False,
        "next_node": None,
        "messages": [ai_message],
    }

