# 图谱构建节点
"""
图谱构建 Agent: 将提取的数据构建到 Neo4j 知识图谱中
"""

from langchain_core.messages import AIMessage

from src.knowledge import (
    Company, Drug, Indication, Trial, EndpointData,
    TreatsRelation, OutputsRelation, CombinedWithRelation,
    get_neo4j_client,
)
from src.knowledge.models.nodes import (
    MoleculeType, TrialDesign, TrialPhase, TrialStatus, TreatmentLine
)
from src.utils import get_logger

from ..state import (
    ExtractedEntity,
    Task,
    TaskStatus,
    WorkflowState,
)

logger = get_logger(__name__)


def _create_node_from_entity(entity: ExtractedEntity):
    """从提取的实体创建节点对象"""
    data = entity.data.copy()
    entity_type = entity.entity_type
    
    try:
        if entity_type == "Drug":
            # 处理枚举类型
            molecule_type = data.get("molecule_type", "其他")
            if isinstance(molecule_type, str):
                try:
                    molecule_type = MoleculeType(molecule_type)
                except ValueError:
                    molecule_type = MoleculeType.OTHER
            data["molecule_type"] = molecule_type
            
            return Drug(**data)
            
        elif entity_type == "Company":
            return Company(**data)
            
        elif entity_type == "Indication":
            return Indication(**data)
            
        elif entity_type == "Trial":
            # 处理枚举类型
            if "design" in data and isinstance(data["design"], str):
                try:
                    data["design"] = TrialDesign(data["design"])
                except ValueError:
                    data["design"] = TrialDesign.OPEN_LABEL
                    
            if "phase" in data and isinstance(data["phase"], str):
                try:
                    data["phase"] = TrialPhase(data["phase"])
                except ValueError:
                    data["phase"] = TrialPhase.PHASE_2
                    
            if "status" in data and isinstance(data["status"], str):
                try:
                    data["status"] = TrialStatus(data["status"])
                except ValueError:
                    data["status"] = TrialStatus.RECRUITING
                    
            return Trial(**data)
            
        elif entity_type == "EndpointData":
            return EndpointData(**data)
            
        else:
            logger.warning(f"Unknown entity type: {entity_type}")
            return None
            
    except Exception as e:
        logger.error(f"Error creating node from entity: {e}")
        return None


async def graph_builder_node(state: WorkflowState) -> dict:
    """图谱构建节点
    
    将提取的实体写入 Neo4j 知识图谱。
    """
    logger.info("Graph builder node processing...")
    
    task = state.current_task
    if not task:
        return {
            "next_node": "coordinator",
            "messages": [AIMessage(content="[图谱构建器] 没有待处理的任务")],
        }
    
    task.status = TaskStatus.IN_PROGRESS
    
    # 获取待处理的实体
    entities_to_process = state.extracted_entities
    if not entities_to_process:
        task.status = TaskStatus.COMPLETED
        task.result = {"message": "No entities to process"}
        return {
            "current_task": None,
            "completed_tasks": state.completed_tasks + [task],
            "next_node": "coordinator",
            "messages": [AIMessage(content="[图谱构建器] 没有待处理的实体")],
        }
    
    # 获取 Neo4j 客户端
    client = get_neo4j_client()
    
    created_nodes = []
    failed_nodes = []
    
    try:
        await client.connect()
        
        for entity in entities_to_process:
            node = _create_node_from_entity(entity)
            if node is None:
                failed_nodes.append(entity.entity_type)
                continue
            
            try:
                node_id = await client.create_node(node)
                created_nodes.append({
                    "id": node_id,
                    "type": entity.entity_type,
                    "name": entity.data.get("name", "N/A"),
                })
                logger.info(f"Created node: {entity.entity_type} - {node_id}")
                
            except Exception as e:
                logger.error(f"Failed to create node: {e}")
                failed_nodes.append(entity.entity_type)
        
    except Exception as e:
        logger.error(f"Neo4j connection error: {e}")
        task.status = TaskStatus.FAILED
        task.error = str(e)
        return {
            "current_task": None,
            "completed_tasks": state.completed_tasks + [task],
            "next_node": "coordinator",
            "messages": [AIMessage(content=f"[图谱构建器] 数据库连接失败: {e}")],
        }
    
    # 更新任务结果
    task.status = TaskStatus.COMPLETED
    task.result = {
        "created_count": len(created_nodes),
        "failed_count": len(failed_nodes),
        "created_nodes": created_nodes,
    }
    
    # 构建响应消息
    summary = f"[图谱构建器] 创建了 {len(created_nodes)} 个节点:\n"
    for node in created_nodes:
        summary += f"  - {node['type']}: {node['name']} (ID: {node['id'][:8]}...)\n"
    
    if failed_nodes:
        summary += f"\n失败: {len(failed_nodes)} 个\n"
    
    return {
        "current_task": None,
        "completed_tasks": state.completed_tasks + [task],
        "created_nodes": state.created_nodes + [n["id"] for n in created_nodes],
        "extracted_entities": [],  # 清空已处理的实体
        "next_node": "coordinator",
        "messages": [AIMessage(content=summary)],
    }

