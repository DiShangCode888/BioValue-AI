# BioValue-AI SDK 客户端
"""
BioValue-AI Python SDK 客户端实现
"""

from typing import Any, Optional
import httpx

from .models import (
    Drug,
    Company,
    Indication,
    Trial,
    EndpointData,
    CompetitionAnalysisResult,
    OpportunityResult,
    IntegrityCheckResult,
    WorkflowResult,
    ChatResponse,
    GraphStatistics,
    QueryResult,
    AffectedCombo,
    OpportunityIndication,
    SuspiciousData,
)


class BioValueError(Exception):
    """SDK 错误基类"""
    pass


class APIError(BioValueError):
    """API 调用错误"""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API Error {status_code}: {detail}")


class BioValueClient:
    """BioValue-AI SDK 客户端
    
    提供对 BioValue-AI API 的便捷访问。
    
    Example:
        ```python
        client = BioValueClient(base_url="http://localhost:8000")
        
        # 创建药物
        drug = client.create_drug(
            name="Pembrolizumab",
            molecule_type="单抗",
            target="PD-1",
            moa="PD-1抑制剂"
        )
        
        # 竞争分析
        result = client.analyze_competition(drug.id, "nsclc_001")
        ```
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 60.0,
        api_key: Optional[str] = None,
    ):
        """初始化客户端
        
        Args:
            base_url: API 服务地址
            timeout: 请求超时时间（秒）
            api_key: API 密钥（可选）
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key
        self._client: Optional[httpx.Client] = None
    
    @property
    def client(self) -> httpx.Client:
        """获取 HTTP 客户端"""
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            self._client = httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client
    
    def close(self):
        """关闭客户端"""
        if self._client:
            self._client.close()
            self._client = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
    
    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> dict:
        """发送请求"""
        response = self.client.request(method, endpoint, **kwargs)
        
        if response.status_code >= 400:
            detail = response.json().get("detail", response.text)
            raise APIError(response.status_code, detail)
        
        return response.json()
    
    # ==================== 节点操作 ====================
    
    def create_drug(
        self,
        name: str,
        molecule_type: str,
        target: str,
        moa: str,
        **kwargs
    ) -> Drug:
        """创建药物节点"""
        data = {
            "name": name,
            "molecule_type": molecule_type,
            "target": target,
            "moa": moa,
            **kwargs
        }
        
        result = self._request(
            "POST",
            "/api/v1/graph/nodes",
            json={"node_type": "Drug", "data": data}
        )
        
        return Drug(id=result["id"], **result["data"])
    
    def create_company(
        self,
        name: str,
        **kwargs
    ) -> Company:
        """创建公司节点"""
        data = {"name": name, **kwargs}
        
        result = self._request(
            "POST",
            "/api/v1/graph/nodes",
            json={"node_type": "Company", "data": data}
        )
        
        return Company(id=result["id"], **result["data"])
    
    def create_indication(
        self,
        name: str,
        **kwargs
    ) -> Indication:
        """创建适应症节点"""
        data = {"name": name, **kwargs}
        
        result = self._request(
            "POST",
            "/api/v1/graph/nodes",
            json={"node_type": "Indication", "data": data}
        )
        
        return Indication(id=result["id"], **result["data"])
    
    def create_trial(
        self,
        nct_id: str,
        title: str,
        design: str,
        phase: str,
        status: str,
        **kwargs
    ) -> Trial:
        """创建临床试验节点"""
        data = {
            "nct_id": nct_id,
            "title": title,
            "design": design,
            "phase": phase,
            "status": status,
            **kwargs
        }
        
        result = self._request(
            "POST",
            "/api/v1/graph/nodes",
            json={"node_type": "Trial", "data": data}
        )
        
        return Trial(id=result["id"], **result["data"])
    
    def get_node(self, node_id: str, node_type: Optional[str] = None) -> dict:
        """获取节点"""
        params = {}
        if node_type:
            params["node_type"] = node_type
        
        return self._request("GET", f"/api/v1/graph/nodes/{node_id}", params=params)
    
    def delete_node(self, node_id: str) -> bool:
        """删除节点"""
        self._request("DELETE", f"/api/v1/graph/nodes/{node_id}")
        return True
    
    def list_drugs(self, limit: int = 100, skip: int = 0) -> list[Drug]:
        """列出药物"""
        result = self._request(
            "GET",
            "/api/v1/graph/nodes",
            params={"node_type": "Drug", "limit": limit, "skip": skip}
        )
        return [Drug(id=n["id"], **n["data"]) for n in result]
    
    # ==================== 边操作 ====================
    
    def create_treats_relation(
        self,
        drug_id: str,
        indication_id: str,
        treatment_line: Optional[str] = None,
        priority: Optional[int] = None,
        **kwargs
    ) -> str:
        """创建药物-适应症治疗关系"""
        data = {**kwargs}
        if treatment_line:
            data["treatment_line"] = treatment_line
        if priority:
            data["priority"] = priority
        
        result = self._request(
            "POST",
            "/api/v1/graph/edges",
            json={
                "edge_type": "TREATS",
                "source_id": drug_id,
                "target_id": indication_id,
                "data": data
            }
        )
        
        return result["id"]
    
    def create_combined_with_relation(
        self,
        drug_a_id: str,
        drug_b_id: str,
        synergy_score: Optional[float] = None,
        **kwargs
    ) -> str:
        """创建联合用药关系"""
        data = {**kwargs}
        if synergy_score is not None:
            data["synergy_score"] = synergy_score
        
        result = self._request(
            "POST",
            "/api/v1/graph/edges",
            json={
                "edge_type": "COMBINED_WITH",
                "source_id": drug_a_id,
                "target_id": drug_b_id,
                "data": data
            }
        )
        
        return result["id"]
    
    # ==================== 查询操作 ====================
    
    def query(self, cypher: str, parameters: Optional[dict] = None) -> QueryResult:
        """执行 Cypher 查询"""
        result = self._request(
            "POST",
            "/api/v1/graph/query",
            json={"query": cypher, "parameters": parameters or {}}
        )
        
        return QueryResult(**result)
    
    def get_statistics(self) -> GraphStatistics:
        """获取图谱统计"""
        result = self._request("GET", "/api/v1/graph/statistics")
        return GraphStatistics(**result)
    
    # ==================== 分析操作 ====================
    
    def analyze_competition(
        self,
        failed_drug_id: str,
        failed_indication_id: str,
        include_llm_analysis: bool = True,
    ) -> CompetitionAnalysisResult:
        """竞争坍缩分析
        
        分析药物失败对联合用药方案的影响。
        
        Args:
            failed_drug_id: 失败药物ID
            failed_indication_id: 失败的适应症ID
            include_llm_analysis: 是否包含LLM分析
            
        Returns:
            CompetitionAnalysisResult: 分析结果
        """
        result = self._request(
            "POST",
            "/api/v1/analysis/competition",
            json={
                "failed_drug_id": failed_drug_id,
                "failed_indication_id": failed_indication_id,
                "include_llm_analysis": include_llm_analysis,
            }
        )
        
        # 转换 affected_combinations
        combos = [AffectedCombo(**c) for c in result.get("affected_combinations", [])]
        result["affected_combinations"] = combos
        
        return CompetitionAnalysisResult(**result)
    
    def discover_opportunities(
        self,
        min_prevalence: int = 10000,
        max_soc_score: float = 6.0,
        min_unmet_need: float = 7.0,
        include_llm_analysis: bool = True,
    ) -> OpportunityResult:
        """空白点挖掘
        
        发现高价值投资机会。
        
        Args:
            min_prevalence: 最小患病人数
            max_soc_score: 最大SoC疗效评分
            min_unmet_need: 最小未满足需求分数
            include_llm_analysis: 是否包含LLM分析
            
        Returns:
            OpportunityResult: 挖掘结果
        """
        result = self._request(
            "POST",
            "/api/v1/analysis/opportunity",
            json={
                "min_prevalence": min_prevalence,
                "max_soc_score": max_soc_score,
                "min_unmet_need": min_unmet_need,
                "include_llm_analysis": include_llm_analysis,
            }
        )
        
        # 转换 high_priority
        high = [OpportunityIndication(**o) for o in result.get("high_priority", [])]
        result["high_priority"] = high
        
        return OpportunityResult(**result)
    
    def check_integrity(
        self,
        p_value_threshold: float = 0.05,
        censoring_threshold: float = 0.5,
        include_llm_analysis: bool = True,
    ) -> IntegrityCheckResult:
        """数据诚信检查
        
        识别可疑的临床数据。
        
        Args:
            p_value_threshold: p值阈值
            censoring_threshold: 删失密度阈值
            include_llm_analysis: 是否包含LLM分析
            
        Returns:
            IntegrityCheckResult: 检查结果
        """
        result = self._request(
            "POST",
            "/api/v1/analysis/integrity",
            json={
                "p_value_threshold": p_value_threshold,
                "censoring_threshold": censoring_threshold,
                "include_llm_analysis": include_llm_analysis,
            }
        )
        
        # 转换 suspicious_data
        suspicious = [SuspiciousData(**s) for s in result.get("suspicious_data", [])]
        result["suspicious_data"] = suspicious
        
        return IntegrityCheckResult(**result)
    
    # ==================== 工作流操作 ====================
    
    def run_workflow(
        self,
        query: str,
        session_id: str = "default",
        max_iterations: int = 10,
    ) -> WorkflowResult:
        """运行完整工作流
        
        Args:
            query: 用户查询
            session_id: 会话ID
            max_iterations: 最大迭代次数
            
        Returns:
            WorkflowResult: 工作流结果
        """
        result = self._request(
            "POST",
            "/api/v1/workflow/run",
            json={
                "query": query,
                "session_id": session_id,
                "max_iterations": max_iterations,
            }
        )
        
        return WorkflowResult(
            session_id=result["session_id"],
            query=result["query"],
            final_report=result["final_report"],
            summary=result["summary"],
            completed_tasks_count=len(result.get("completed_tasks", [])),
            analysis_results_count=len(result.get("analysis_results", [])),
            extracted_entities_count=result.get("extracted_entities_count", 0),
            created_nodes_count=result.get("created_nodes_count", 0),
        )
    
    def chat(self, message: str, session_id: str = "default") -> ChatResponse:
        """对话
        
        Args:
            message: 用户消息
            session_id: 会话ID
            
        Returns:
            ChatResponse: 对话响应
        """
        result = self._request(
            "POST",
            "/api/v1/workflow/chat",
            json={"message": message, "session_id": session_id}
        )
        
        return ChatResponse(**result)
    
    # ==================== 数据摄入操作 ====================
    
    def search_clinical_trials(
        self,
        query: Optional[str] = None,
        condition: Optional[str] = None,
        intervention: Optional[str] = None,
        page_size: int = 20,
    ) -> list[dict]:
        """搜索 ClinicalTrials.gov"""
        result = self._request(
            "POST",
            "/api/v1/data/clinical-trials/search",
            json={
                "query": query,
                "condition": condition,
                "intervention": intervention,
                "page_size": page_size,
            }
        )
        
        return result
    
    def import_clinical_trial(self, nct_id: str) -> dict:
        """导入临床试验到知识图谱"""
        return self._request("POST", f"/api/v1/data/clinical-trials/import/{nct_id}")
    
    # ==================== 健康检查 ====================
    
    def health_check(self) -> dict:
        """健康检查"""
        return self._request("GET", "/health")

