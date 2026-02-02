# 数据提取节点
"""
数据提取 Agent: 从各种数据源提取结构化信息
支持:
- PDF 文档解析
- 网页内容提取
- 外部 API 数据获取
"""

from langchain_core.messages import AIMessage

from src.llms import get_llm
from src.knowledge.models import (
    Company, Drug, Indication, Trial, EndpointData
)
from src.utils import get_logger

from ..state import (
    ExtractedEntity,
    ExtractionPlan,
    Task,
    TaskStatus,
    WorkflowState,
)

logger = get_logger(__name__)

EXTRACTOR_SYSTEM_PROMPT = """你是 BioValue-AI 的数据提取专家 Agent。

你的职责是从文本中提取创新药相关的结构化数据，包括:

1. 公司信息 (Company):
   - 名称、股票代码
   - 现金余额、融资轮次、研发费用占比
   - 科学家背景评分

2. 药物信息 (Drug):
   - 名称（通用名/商品名）
   - 分子类型（ADC/单抗/双抗/小分子等）
   - 靶点、作用机制
   - 专利失效日、给药方式

3. 适应症信息 (Indication):
   - 名称
   - 流行病学数据
   - 当前标准疗法(SoC)
   - 未满足需求程度

4. 临床实验信息 (Trial):
   - NCT编号
   - 实验设计、阶段、状态
   - 入组人数、治疗线数

5. 终点数据 (EndpointData):
   - mPFS、mOS、ORR
   - HR值及95%CI、p值
   - 不良反应率

请仔细分析文本，提取所有可识别的实体和属性。
对于不确定的信息，标注置信度。
"""

# 实体提取的 schema 定义
ENTITY_SCHEMAS = {
    "Drug": {
        "required": ["name", "molecule_type", "target", "moa"],
        "optional": ["name_en", "loe_date", "administration_route"]
    },
    "Company": {
        "required": ["name"],
        "optional": ["cash_balance", "funding_round", "rd_expense_ratio", "scientist_background_score"]
    },
    "Indication": {
        "required": ["name"],
        "optional": ["prevalence", "current_soc", "unmet_need_score"]
    },
    "Trial": {
        "required": ["nct_id", "title", "design", "phase", "status"],
        "optional": ["enrollment_target", "treatment_line", "primary_endpoint"]
    },
    "EndpointData": {
        "required": ["trial_id"],
        "optional": ["mpfs_months", "mos_months", "orr_percent", "hr_pfs", "hr_pfs_p_value", "grade3_plus_ae_rate"]
    }
}


async def extractor_node(state: WorkflowState) -> dict:
    """数据提取节点
    
    从文档或文本中提取结构化数据。
    """
    logger.info("Extractor node processing...")
    
    task = state.current_task
    if not task:
        return {
            "next_node": "coordinator",
            "messages": [AIMessage(content="[提取器] 没有待处理的任务")],
        }
    
    # 更新任务状态
    task.status = TaskStatus.IN_PROGRESS
    
    # 获取要提取的文本
    text_to_extract = task.parameters.get("text", "")
    source = task.parameters.get("source", "unknown")
    target_entities = task.parameters.get("target_entities", ["Drug", "Company", "Trial"])
    
    if not text_to_extract:
        # 如果没有文本，尝试从用户查询中提取
        text_to_extract = state.user_query
    
    if not text_to_extract:
        task.status = TaskStatus.FAILED
        task.error = "No text provided for extraction"
        return {
            "current_task": task,
            "completed_tasks": state.completed_tasks + [task],
            "next_node": "coordinator",
            "messages": [AIMessage(content="[提取器] 没有提供待提取的文本")],
        }
    
    # 使用 LLM 提取实体
    llm = get_llm("extraction")
    
    extracted_entities = []
    
    for entity_type in target_entities:
        schema = ENTITY_SCHEMAS.get(entity_type)
        if not schema:
            continue
        
        extraction_prompt = f"""请从以下文本中提取所有 {entity_type} 实体:

文本:
{text_to_extract}

需要提取的字段:
- 必填: {', '.join(schema['required'])}
- 可选: {', '.join(schema['optional'])}

请以 JSON 数组格式返回提取结果，每个对象代表一个实体。
如果某字段无法从文本中确定，请省略该字段。
同时为每个实体提供一个 confidence 字段（0-1），表示提取的置信度。
"""
        
        try:
            response = await llm.generate(
                prompt=extraction_prompt,
                system_prompt=EXTRACTOR_SYSTEM_PROMPT,
                temperature=0,
            )
            
            # 解析响应
            import json
            content = response.content
            
            # 提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            try:
                entities_data = json.loads(content.strip())
                if not isinstance(entities_data, list):
                    entities_data = [entities_data]
                
                for entity_data in entities_data:
                    confidence = entity_data.pop("confidence", 0.8)
                    extracted_entities.append(
                        ExtractedEntity(
                            entity_type=entity_type,
                            data=entity_data,
                            source=source,
                            confidence=confidence,
                        )
                    )
                    
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse extraction result for {entity_type}")
                
        except Exception as e:
            logger.error(f"Extraction error for {entity_type}: {e}")
    
    # 更新任务结果
    task.status = TaskStatus.COMPLETED
    task.result = {
        "extracted_count": len(extracted_entities),
        "entity_types": list(set(e.entity_type for e in extracted_entities)),
    }
    
    # 构建响应消息
    summary = f"[提取器] 从文本中提取了 {len(extracted_entities)} 个实体:\n"
    for entity in extracted_entities:
        summary += f"  - {entity.entity_type}: {entity.data.get('name', 'N/A')} (置信度: {entity.confidence:.2f})\n"
    
    return {
        "current_task": None,
        "completed_tasks": state.completed_tasks + [task],
        "extracted_entities": state.extracted_entities + extracted_entities,
        "next_node": "coordinator",
        "messages": [AIMessage(content=summary)],
    }

