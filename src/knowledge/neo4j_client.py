# Neo4j 客户端封装
"""
Neo4j 图数据库客户端，提供:
- 连接管理
- CRUD 操作
- 事务支持
- 查询模板执行
"""

from contextlib import asynccontextmanager
from typing import Any, TypeVar

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from pydantic import BaseModel

from src.config import get_settings
from src.utils import get_logger

from .models.nodes import BaseNode, NodeType
from .models.edges import BaseEdge, EdgeType

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseNode)
E = TypeVar("E", bound=BaseEdge)

# 全局客户端实例
_neo4j_client: "Neo4jClient | None" = None


class Neo4jClient:
    """Neo4j 异步客户端
    
    封装 Neo4j 数据库操作，支持:
    - 节点 CRUD
    - 关系 CRUD
    - 复杂查询
    - 事务管理
    """
    
    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str = "neo4j",
    ):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self._driver: AsyncDriver | None = None
    
    async def connect(self) -> None:
        """建立数据库连接"""
        if self._driver is None:
            logger.info(f"Connecting to Neo4j at {self.uri}")
            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
            )
            # 验证连接
            await self._driver.verify_connectivity()
            logger.info("Neo4j connection established")
    
    async def close(self) -> None:
        """关闭数据库连接"""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed")
    
    @asynccontextmanager
    async def session(self):
        """获取数据库会话"""
        if self._driver is None:
            await self.connect()
        
        session = self._driver.session(database=self.database)
        try:
            yield session
        finally:
            await session.close()
    
    # ==================== 节点操作 ====================
    
    async def create_node(self, node: BaseNode) -> str:
        """创建节点
        
        Args:
            node: 节点对象
            
        Returns:
            str: 节点ID
        """
        async with self.session() as session:
            properties = node.to_neo4j_properties()
            label = node.node_type.value
            
            query = f"""
            CREATE (n:{label} $props)
            RETURN n.id as id
            """
            
            result = await session.run(query, props=properties)
            record = await result.single()
            logger.debug(f"Created node: {label} with id {record['id']}")
            return record["id"]
    
    async def get_node(
        self,
        node_id: str,
        node_type: NodeType | None = None
    ) -> dict | None:
        """获取节点
        
        Args:
            node_id: 节点ID
            node_type: 节点类型(可选，用于优化查询)
            
        Returns:
            dict | None: 节点属性字典
        """
        async with self.session() as session:
            if node_type:
                query = f"""
                MATCH (n:{node_type.value} {{id: $id}})
                RETURN n
                """
            else:
                query = """
                MATCH (n {id: $id})
                RETURN n
                """
            
            result = await session.run(query, id=node_id)
            record = await result.single()
            
            if record:
                return dict(record["n"])
            return None
    
    async def update_node(self, node: BaseNode) -> bool:
        """更新节点
        
        Args:
            node: 节点对象
            
        Returns:
            bool: 是否更新成功
        """
        async with self.session() as session:
            properties = node.to_neo4j_properties()
            label = node.node_type.value
            
            query = f"""
            MATCH (n:{label} {{id: $id}})
            SET n += $props
            RETURN n.id as id
            """
            
            result = await session.run(
                query,
                id=node.id,
                props=properties
            )
            record = await result.single()
            return record is not None
    
    async def delete_node(self, node_id: str) -> bool:
        """删除节点及其关联关系
        
        Args:
            node_id: 节点ID
            
        Returns:
            bool: 是否删除成功
        """
        async with self.session() as session:
            query = """
            MATCH (n {id: $id})
            DETACH DELETE n
            RETURN count(n) as deleted
            """
            
            result = await session.run(query, id=node_id)
            record = await result.single()
            return record["deleted"] > 0
    
    async def find_nodes(
        self,
        node_type: NodeType,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict]:
        """查找节点
        
        Args:
            node_type: 节点类型
            filters: 过滤条件
            limit: 返回数量限制
            skip: 跳过数量
            
        Returns:
            list[dict]: 节点列表
        """
        async with self.session() as session:
            where_clause = ""
            if filters:
                conditions = [f"n.{k} = ${k}" for k in filters.keys()]
                where_clause = "WHERE " + " AND ".join(conditions)
            
            query = f"""
            MATCH (n:{node_type.value})
            {where_clause}
            RETURN n
            ORDER BY n.created_at DESC
            SKIP $skip
            LIMIT $limit
            """
            
            params = {"skip": skip, "limit": limit}
            if filters:
                params.update(filters)
            
            result = await session.run(query, **params)
            records = await result.data()
            return [dict(r["n"]) for r in records]
    
    # ==================== 关系操作 ====================
    
    async def create_edge(self, edge: BaseEdge) -> str:
        """创建关系
        
        Args:
            edge: 关系对象
            
        Returns:
            str: 关系ID
        """
        async with self.session() as session:
            properties = edge.to_neo4j_properties()
            rel_type = edge.edge_type.value
            
            query = f"""
            MATCH (a {{id: $source_id}})
            MATCH (b {{id: $target_id}})
            CREATE (a)-[r:{rel_type} $props]->(b)
            RETURN r.id as id
            """
            
            result = await session.run(
                query,
                source_id=edge.source_id,
                target_id=edge.target_id,
                props=properties
            )
            record = await result.single()
            
            if record is None:
                raise ValueError(
                    f"Failed to create edge: source={edge.source_id}, "
                    f"target={edge.target_id}"
                )
            
            logger.debug(f"Created edge: {rel_type} with id {record['id']}")
            return record["id"]
    
    async def get_edge(self, edge_id: str) -> dict | None:
        """获取关系"""
        async with self.session() as session:
            query = """
            MATCH ()-[r {id: $id}]->()
            RETURN r, type(r) as type
            """
            
            result = await session.run(query, id=edge_id)
            record = await result.single()
            
            if record:
                data = dict(record["r"])
                data["edge_type"] = record["type"]
                return data
            return None
    
    async def delete_edge(self, edge_id: str) -> bool:
        """删除关系"""
        async with self.session() as session:
            query = """
            MATCH ()-[r {id: $id}]->()
            DELETE r
            RETURN count(r) as deleted
            """
            
            result = await session.run(query, id=edge_id)
            record = await result.single()
            return record["deleted"] > 0
    
    async def find_edges(
        self,
        edge_type: EdgeType,
        source_id: str | None = None,
        target_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """查找关系"""
        async with self.session() as session:
            conditions = []
            params = {"limit": limit}
            
            if source_id:
                conditions.append("a.id = $source_id")
                params["source_id"] = source_id
            if target_id:
                conditions.append("b.id = $target_id")
                params["target_id"] = target_id
            
            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)
            
            query = f"""
            MATCH (a)-[r:{edge_type.value}]->(b)
            {where_clause}
            RETURN r, a.id as source_id, b.id as target_id
            LIMIT $limit
            """
            
            result = await session.run(query, **params)
            records = await result.data()
            
            edges = []
            for r in records:
                edge_data = dict(r["r"])
                edge_data["source_id"] = r["source_id"]
                edge_data["target_id"] = r["target_id"]
                edges.append(edge_data)
            
            return edges
    
    # ==================== 复杂查询 ====================
    
    async def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None
    ) -> list[dict]:
        """执行自定义 Cypher 查询
        
        Args:
            query: Cypher 查询语句
            parameters: 查询参数
            
        Returns:
            list[dict]: 查询结果
        """
        async with self.session() as session:
            result = await session.run(query, **(parameters or {}))
            return await result.data()
    
    async def get_drug_by_indication(
        self,
        indication_id: str,
        treatment_line: str | None = None
    ) -> list[dict]:
        """获取某适应症下的所有药物
        
        Args:
            indication_id: 适应症ID
            treatment_line: 治疗线数过滤
            
        Returns:
            list[dict]: 药物列表及其治疗关系
        """
        conditions = ["i.id = $indication_id"]
        params = {"indication_id": indication_id}
        
        if treatment_line:
            conditions.append("r.treatment_line = $treatment_line")
            params["treatment_line"] = treatment_line
        
        query = f"""
        MATCH (d:Drug)-[r:TREATS]->(i:Indication)
        WHERE {' AND '.join(conditions)}
        RETURN d, r
        ORDER BY r.priority DESC
        """
        
        return await self.execute_query(query, params)
    
    async def get_drug_combinations(self, drug_id: str) -> list[dict]:
        """获取某药物的所有联合用药方案
        
        Args:
            drug_id: 药物ID
            
        Returns:
            list[dict]: 联合用药信息
        """
        query = """
        MATCH (d1:Drug {id: $drug_id})-[r:COMBINED_WITH]-(d2:Drug)
        OPTIONAL MATCH (d1)-[:PART_OF_COMBO]->(combo:ComboNode)<-[:PART_OF_COMBO]-(d2)
        RETURN d2, r, combo
        """
        
        return await self.execute_query(query, {"drug_id": drug_id})
    
    async def get_trial_with_endpoints(self, trial_id: str) -> dict | None:
        """获取临床实验及其终点数据
        
        Args:
            trial_id: 实验ID
            
        Returns:
            dict: 实验信息及终点数据
        """
        query = """
        MATCH (t:Trial {id: $trial_id})
        OPTIONAL MATCH (t)-[r:OUTPUTS]->(e:EndpointData)
        OPTIONAL MATCH (e)-[:HAS_LANDMARK]->(l:LandmarkNode)
        RETURN t, collect(DISTINCT e) as endpoints, collect(DISTINCT l) as landmarks
        """
        
        result = await self.execute_query(query, {"trial_id": trial_id})
        return result[0] if result else None
    
    async def get_indication_soc(self, indication_id: str) -> dict | None:
        """获取适应症的标准疗法
        
        Args:
            indication_id: 适应症ID
            
        Returns:
            dict: 标准疗法药物信息
        """
        query = """
        MATCH (i:Indication {id: $indication_id})-[r:HAS_SOC]->(d:Drug)
        WHERE r.is_current_soc = true
        RETURN d, r
        """
        
        result = await self.execute_query(query, {"indication_id": indication_id})
        return result[0] if result else None
    
    async def find_competing_drugs(
        self,
        drug_id: str,
        indication_id: str
    ) -> list[dict]:
        """查找竞争药物
        
        Args:
            drug_id: 药物ID
            indication_id: 适应症ID
            
        Returns:
            list[dict]: 竞争药物列表
        """
        query = """
        MATCH (d:Drug {id: $drug_id})-[:TREATS]->(i:Indication {id: $indication_id})
        MATCH (competitor:Drug)-[r:TREATS]->(i)
        WHERE competitor.id <> $drug_id
        OPTIONAL MATCH (competitor)-[:OUTPUTS]->(:Trial)-[:OUTPUTS]->(e:EndpointData)
        RETURN competitor, r, collect(e) as endpoints
        ORDER BY r.priority DESC
        """
        
        return await self.execute_query(
            query,
            {"drug_id": drug_id, "indication_id": indication_id}
        )
    
    # ==================== 图谱统计 ====================
    
    async def get_statistics(self) -> dict:
        """获取图谱统计信息"""
        query = """
        MATCH (n)
        WITH labels(n) as labels, count(*) as count
        UNWIND labels as label
        RETURN label, sum(count) as node_count
        ORDER BY node_count DESC
        """
        
        node_stats = await self.execute_query(query)
        
        edge_query = """
        MATCH ()-[r]->()
        RETURN type(r) as edge_type, count(*) as edge_count
        ORDER BY edge_count DESC
        """
        
        edge_stats = await self.execute_query(edge_query)
        
        return {
            "nodes": {r["label"]: r["node_count"] for r in node_stats},
            "edges": {r["edge_type"]: r["edge_count"] for r in edge_stats},
        }


def get_neo4j_client() -> Neo4jClient:
    """获取 Neo4j 客户端单例"""
    global _neo4j_client
    
    if _neo4j_client is None:
        settings = get_settings()
        _neo4j_client = Neo4jClient(
            uri=settings.neo4j.uri,
            username=settings.neo4j.username,
            password=settings.neo4j.password,
            database=settings.neo4j.database,
        )
    
    return _neo4j_client


async def init_neo4j_schema(client: Neo4jClient) -> None:
    """初始化 Neo4j 索引和约束
    
    Args:
        client: Neo4j 客户端
    """
    async with client.session() as session:
        # 创建唯一约束
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Company) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Drug) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Indication) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Trial) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Trial) REQUIRE n.nct_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:EndpointData) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:MediaAsset) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ExternalFactor) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ComboNode) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:LandmarkNode) REQUIRE n.id IS UNIQUE",
        ]
        
        # 创建索引
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (n:Drug) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Drug) ON (n.target)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Indication) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Company) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Trial) ON (n.status)",
        ]
        
        for query in constraints + indexes:
            await session.run(query)
        
        logger.info("Neo4j schema initialized")

