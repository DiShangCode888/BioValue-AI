# 图谱操作路由
"""
知识图谱 CRUD 操作 API
"""

from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.knowledge import (
    get_neo4j_client,
    Company, Drug, Indication, Trial, EndpointData,
    TreatsRelation, CombinedWithRelation,
)
from src.knowledge.models.nodes import NodeType
from src.knowledge.models.edges import EdgeType
from src.utils import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ==================== 请求/响应模型 ====================

class NodeCreateRequest(BaseModel):
    """节点创建请求"""
    node_type: str
    data: dict[str, Any]


class NodeResponse(BaseModel):
    """节点响应"""
    id: str
    node_type: str
    data: dict[str, Any]


class EdgeCreateRequest(BaseModel):
    """边创建请求"""
    edge_type: str
    source_id: str
    target_id: str
    data: dict[str, Any] = Field(default_factory=dict)


class EdgeResponse(BaseModel):
    """边响应"""
    id: str
    edge_type: str
    source_id: str
    target_id: str
    data: dict[str, Any]


class QueryRequest(BaseModel):
    """Cypher 查询请求"""
    query: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    """查询响应"""
    results: list[dict[str, Any]]
    count: int


# ==================== 节点操作 ====================

@router.post("/nodes", response_model=NodeResponse)
async def create_node(request: NodeCreateRequest):
    """创建节点
    
    支持的节点类型:
    - Company: 公司
    - Drug: 药物
    - Indication: 适应症
    - Trial: 临床实验
    - EndpointData: 终点数据
    """
    client = get_neo4j_client()
    
    try:
        node_type = NodeType(request.node_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid node type: {request.node_type}"
        )
    
    # 创建节点对象
    node_classes = {
        NodeType.COMPANY: Company,
        NodeType.DRUG: Drug,
        NodeType.INDICATION: Indication,
        NodeType.TRIAL: Trial,
        NodeType.ENDPOINT_DATA: EndpointData,
    }
    
    node_class = node_classes.get(node_type)
    if not node_class:
        raise HTTPException(
            status_code=400,
            detail=f"Node type not supported: {request.node_type}"
        )
    
    try:
        node = node_class(**request.data)
        await client.connect()
        node_id = await client.create_node(node)
        
        return NodeResponse(
            id=node_id,
            node_type=request.node_type,
            data=node.to_neo4j_properties(),
        )
    except Exception as e:
        logger.error(f"Failed to create node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes/{node_id}", response_model=NodeResponse)
async def get_node(node_id: str, node_type: str | None = None):
    """获取节点"""
    client = get_neo4j_client()
    
    try:
        await client.connect()
        nt = NodeType(node_type) if node_type else None
        node_data = await client.get_node(node_id, nt)
        
        if not node_data:
            raise HTTPException(status_code=404, detail="Node not found")
        
        return NodeResponse(
            id=node_id,
            node_type=node_type or "unknown",
            data=node_data,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: str):
    """删除节点"""
    client = get_neo4j_client()
    
    try:
        await client.connect()
        success = await client.delete_node(node_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Node not found")
        
        return {"message": "Node deleted", "id": node_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes", response_model=list[NodeResponse])
async def list_nodes(
    node_type: str,
    limit: int = Query(default=100, le=1000),
    skip: int = Query(default=0, ge=0),
):
    """列出节点"""
    client = get_neo4j_client()
    
    try:
        nt = NodeType(node_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid node type: {node_type}"
        )
    
    try:
        await client.connect()
        nodes = await client.find_nodes(nt, limit=limit, skip=skip)
        
        return [
            NodeResponse(
                id=n.get("id", ""),
                node_type=node_type,
                data=n,
            )
            for n in nodes
        ]
    except Exception as e:
        logger.error(f"Failed to list nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 边操作 ====================

@router.post("/edges", response_model=EdgeResponse)
async def create_edge(request: EdgeCreateRequest):
    """创建关联
    
    支持的关联类型:
    - TREATS: 药物治疗适应症
    - OUTPUTS: 实验产出数据
    - COMBINED_WITH: 联合用药
    - HAS_SOC: 标准疗法
    """
    client = get_neo4j_client()
    
    try:
        edge_type = EdgeType(request.edge_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid edge type: {request.edge_type}"
        )
    
    # 创建边对象
    edge_classes = {
        EdgeType.TREATS: TreatsRelation,
        EdgeType.COMBINED_WITH: CombinedWithRelation,
    }
    
    edge_class = edge_classes.get(edge_type)
    
    try:
        if edge_class:
            edge = edge_class(
                source_id=request.source_id,
                target_id=request.target_id,
                **request.data
            )
        else:
            # 通用边
            from src.knowledge.models.edges import BaseEdge
            edge = BaseEdge(
                edge_type=edge_type,
                source_id=request.source_id,
                target_id=request.target_id,
            )
        
        await client.connect()
        edge_id = await client.create_edge(edge)
        
        return EdgeResponse(
            id=edge_id,
            edge_type=request.edge_type,
            source_id=request.source_id,
            target_id=request.target_id,
            data=edge.to_neo4j_properties(),
        )
    except Exception as e:
        logger.error(f"Failed to create edge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/edges/{edge_id}", response_model=EdgeResponse)
async def get_edge(edge_id: str):
    """获取关联"""
    client = get_neo4j_client()
    
    try:
        await client.connect()
        edge_data = await client.get_edge(edge_id)
        
        if not edge_data:
            raise HTTPException(status_code=404, detail="Edge not found")
        
        return EdgeResponse(
            id=edge_id,
            edge_type=edge_data.get("edge_type", "unknown"),
            source_id=edge_data.get("source_id", ""),
            target_id=edge_data.get("target_id", ""),
            data=edge_data,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get edge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/edges/{edge_id}")
async def delete_edge(edge_id: str):
    """删除关联"""
    client = get_neo4j_client()
    
    try:
        await client.connect()
        success = await client.delete_edge(edge_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Edge not found")
        
        return {"message": "Edge deleted", "id": edge_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete edge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 查询操作 ====================

@router.post("/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    """执行 Cypher 查询
    
    警告: 请确保查询语句安全，避免注入攻击
    """
    client = get_neo4j_client()
    
    # 基本安全检查
    dangerous_keywords = ["DELETE", "REMOVE", "DROP", "CREATE", "SET", "MERGE"]
    query_upper = request.query.upper()
    
    for keyword in dangerous_keywords:
        if keyword in query_upper and "RETURN" not in query_upper:
            raise HTTPException(
                status_code=400,
                detail=f"Dangerous query detected: {keyword} without RETURN"
            )
    
    try:
        await client.connect()
        results = await client.execute_query(request.query, request.parameters)
        
        return QueryResponse(
            results=results,
            count=len(results),
        )
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics():
    """获取图谱统计信息"""
    client = get_neo4j_client()
    
    try:
        await client.connect()
        stats = await client.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

