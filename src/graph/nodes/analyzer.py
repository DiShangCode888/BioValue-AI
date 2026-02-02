# 分析推理节点
"""
分析 Agent: 执行知识图谱上的高级分析
- 竞争坍缩模拟
- 空白点挖掘
- 数据诚信检查
"""

from langchain_core.messages import AIMessage

from src.knowledge import get_neo4j_client
from src.knowledge.queries import (
    COMPETITION_COLLAPSE_QUERY,
    OPPORTUNITY_DISCOVERY_QUERY,
    DATA_INTEGRITY_CHECK_QUERY,
    DRUG_FULL_PROFILE_QUERY,
    INDICATION_LANDSCAPE_QUERY,
)
from src.llms import get_llm
from src.utils import get_logger

from ..state import (
    AnalysisResult,
    Task,
    TaskStatus,
    TaskType,
    WorkflowState,
)

logger = get_logger(__name__)

ANALYZER_SYSTEM_PROMPT = """你是 BioValue-AI 的投资分析专家 Agent。

你的职责是基于知识图谱数据执行深度分析，为创新药投资提供决策支持。

分析类型:

1. **竞争坍缩模拟** (competition_collapse)
   - 当某药物在特定适应症的实验失败时
   - 找出所有依赖该药物的联合用药方案
   - 评估连锁影响

2. **空白点挖掘** (opportunity_discovery)
   - 搜索高流行病学数据 + 低SoC疗效 + 无在研Phase III管线的适应症
   - 识别投资价值"处女地"

3. **数据诚信预警** (data_integrity)
   - 检查p值极其显著但KM曲线尾部有大量删失点的情况
   - 触发"数据可靠性存疑"标签

请基于查询结果，给出专业的投资分析见解和建议。
"""


async def analyzer_node(state: WorkflowState) -> dict:
    """分析推理节点"""
    logger.info("Analyzer node processing...")
    
    task = state.current_task
    if not task:
        return {
            "next_node": "coordinator",
            "messages": [AIMessage(content="[分析器] 没有待处理的任务")],
        }
    
    task.status = TaskStatus.IN_PROGRESS
    
    # 获取 Neo4j 客户端
    client = get_neo4j_client()
    
    analysis_result = None
    query_results = []
    
    try:
        await client.connect()
        
        # 根据任务类型执行不同的分析
        if task.type == TaskType.ANALYZE_COMPETITION:
            analysis_result = await _analyze_competition(client, task, state)
            
        elif task.type == TaskType.FIND_OPPORTUNITY:
            analysis_result = await _find_opportunity(client, task, state)
            
        elif task.type == TaskType.CHECK_INTEGRITY:
            analysis_result = await _check_integrity(client, task, state)
            
        elif task.type == TaskType.QUERY_GRAPH:
            query_results = await _execute_query(client, task, state)
            
        else:
            # 默认执行通用查询
            query_results = await _execute_query(client, task, state)
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        task.status = TaskStatus.FAILED
        task.error = str(e)
        return {
            "current_task": None,
            "completed_tasks": state.completed_tasks + [task],
            "next_node": "coordinator",
            "messages": [AIMessage(content=f"[分析器] 分析执行失败: {e}")],
        }
    
    # 更新任务状态
    task.status = TaskStatus.COMPLETED
    task.result = {
        "analysis_type": task.type.value,
        "has_result": analysis_result is not None,
        "query_results_count": len(query_results),
    }
    
    # 构建更新
    updates = {
        "current_task": None,
        "completed_tasks": state.completed_tasks + [task],
        "next_node": "coordinator",
    }
    
    if analysis_result:
        updates["analysis_results"] = state.analysis_results + [analysis_result]
        summary = _format_analysis_summary(analysis_result)
    else:
        updates["graph_query_results"] = state.graph_query_results + query_results
        summary = f"[分析器] 查询返回 {len(query_results)} 条结果"
    
    updates["messages"] = [AIMessage(content=summary)]
    
    return updates


async def _analyze_competition(
    client,
    task: Task,
    state: WorkflowState
) -> AnalysisResult:
    """执行竞争坍缩分析"""
    params = task.parameters
    drug_id = params.get("drug_id", "")
    indication_id = params.get("indication_id", "")
    
    # 执行图谱查询
    results = await client.execute_query(
        COMPETITION_COLLAPSE_QUERY,
        {
            "failed_drug_id": drug_id,
            "failed_indication_id": indication_id,
        }
    )
    
    # 使用 LLM 分析结果
    llm = get_llm("reasoning")
    
    analysis_prompt = f"""请分析以下竞争坍缩模拟结果，并给出投资建议:

查询参数:
- 失败药物ID: {drug_id}
- 适应症ID: {indication_id}

图谱查询结果:
{results}

请从以下角度分析:
1. 受影响的联合用药方案数量和重要性
2. 涉及的公司和管线
3. 对该适应症竞争格局的影响
4. 投资建议
"""
    
    response = await llm.generate(
        prompt=analysis_prompt,
        system_prompt=ANALYZER_SYSTEM_PROMPT,
    )
    
    return AnalysisResult(
        analysis_type="competition_collapse",
        findings=[{
            "query_results": results,
            "llm_analysis": response.content,
        }],
        recommendations=_extract_recommendations(response.content),
        confidence_score=0.8,
        raw_data={"query_results": results},
    )


async def _find_opportunity(
    client,
    task: Task,
    state: WorkflowState
) -> AnalysisResult:
    """执行空白点挖掘"""
    params = task.parameters
    
    # 执行图谱查询
    results = await client.execute_query(
        OPPORTUNITY_DISCOVERY_QUERY,
        {
            "min_prevalence": params.get("min_prevalence", 10000),
            "max_soc_score": params.get("max_soc_score", 6),
            "min_unmet_need": params.get("min_unmet_need", 7),
        }
    )
    
    # 使用 LLM 分析结果
    llm = get_llm("reasoning")
    
    analysis_prompt = f"""请分析以下空白点挖掘结果，识别高价值投资机会:

图谱查询结果:
{results}

请从以下角度分析:
1. 识别出的高价值适应症
2. 当前竞争格局
3. 进入壁垒分析
4. 投资优先级排序
5. 具体投资建议
"""
    
    response = await llm.generate(
        prompt=analysis_prompt,
        system_prompt=ANALYZER_SYSTEM_PROMPT,
    )
    
    return AnalysisResult(
        analysis_type="opportunity_discovery",
        findings=[{
            "opportunities": results,
            "llm_analysis": response.content,
        }],
        recommendations=_extract_recommendations(response.content),
        confidence_score=0.75,
        raw_data={"query_results": results},
    )


async def _check_integrity(
    client,
    task: Task,
    state: WorkflowState
) -> AnalysisResult:
    """执行数据诚信检查"""
    params = task.parameters
    
    # 执行图谱查询
    results = await client.execute_query(
        DATA_INTEGRITY_CHECK_QUERY,
        {
            "p_value_threshold": params.get("p_value_threshold", 0.05),
            "censoring_threshold": params.get("censoring_threshold", 0.5),
        }
    )
    
    # 使用 LLM 分析结果
    llm = get_llm("reasoning")
    
    analysis_prompt = f"""请分析以下数据诚信检查结果，识别可疑数据:

图谱查询结果:
{results}

请从以下角度分析:
1. 高风险数据识别
2. 可疑模式说明
3. 需要进一步验证的数据点
4. 投资决策建议
"""
    
    response = await llm.generate(
        prompt=analysis_prompt,
        system_prompt=ANALYZER_SYSTEM_PROMPT,
    )
    
    return AnalysisResult(
        analysis_type="data_integrity",
        findings=[{
            "suspicious_data": results,
            "llm_analysis": response.content,
        }],
        recommendations=_extract_recommendations(response.content),
        confidence_score=0.85,
        raw_data={"query_results": results},
    )


async def _execute_query(
    client,
    task: Task,
    state: WorkflowState
) -> list:
    """执行通用图谱查询"""
    params = task.parameters
    query = params.get("query", "")
    query_params = params.get("params", {})
    
    if not query:
        # 根据用户查询智能选择查询模板
        user_query = state.user_query.lower()
        
        if "药物" in user_query or "drug" in user_query:
            drug_id = params.get("drug_id", "")
            if drug_id:
                query = DRUG_FULL_PROFILE_QUERY
                query_params = {"drug_id": drug_id}
            else:
                return []
                
        elif "适应症" in user_query or "indication" in user_query:
            indication_id = params.get("indication_id", "")
            if indication_id:
                query = INDICATION_LANDSCAPE_QUERY
                query_params = {"indication_id": indication_id}
            else:
                return []
        else:
            return []
    
    return await client.execute_query(query, query_params)


def _extract_recommendations(text: str) -> list[str]:
    """从 LLM 响应中提取建议"""
    recommendations = []
    
    # 简单的建议提取逻辑
    lines = text.split("\n")
    in_recommendation = False
    
    for line in lines:
        line = line.strip()
        if "建议" in line or "recommendation" in line.lower():
            in_recommendation = True
            continue
        
        if in_recommendation and line:
            if line.startswith(("-", "•", "*", "1", "2", "3", "4", "5")):
                # 清理前缀
                clean_line = line.lstrip("-•*0123456789. ")
                if clean_line:
                    recommendations.append(clean_line)
    
    return recommendations[:5]  # 最多返回5条建议


def _format_analysis_summary(result: AnalysisResult) -> str:
    """格式化分析结果摘要"""
    summary = f"[分析器] 完成 {result.analysis_type} 分析\n"
    summary += f"置信度: {result.confidence_score:.2f}\n"
    
    if result.recommendations:
        summary += "\n主要建议:\n"
        for i, rec in enumerate(result.recommendations, 1):
            summary += f"  {i}. {rec}\n"
    
    return summary

