# ClinicalTrials.gov API 客户端
"""
对接 ClinicalTrials.gov API v2
获取临床试验数据
"""

from typing import Any

from pydantic import BaseModel, Field

from src.config import get_settings
from src.knowledge.models.nodes import (
    Trial,
    TrialDesign,
    TrialPhase,
    TrialStatus,
    TreatmentLine,
)
from src.utils import get_logger

from .base import ExternalAPIClient

logger = get_logger(__name__)


class ClinicalTrialStudy(BaseModel):
    """临床试验研究"""
    nct_id: str
    title: str
    status: str
    phase: str | None = None
    enrollment: int | None = None
    start_date: str | None = None
    completion_date: str | None = None
    conditions: list[str] = Field(default_factory=list)
    interventions: list[dict] = Field(default_factory=list)
    sponsors: list[dict] = Field(default_factory=list)
    design: dict = Field(default_factory=dict)
    outcomes: list[dict] = Field(default_factory=list)


class ClinicalTrialsAPI(ExternalAPIClient):
    """ClinicalTrials.gov API 客户端
    
    基于 ClinicalTrials.gov API v2
    文档: https://clinicaltrials.gov/data-api/api
    """
    
    def __init__(self):
        settings = get_settings()
        base_url = settings.ingestion.clinical_trials_api
        super().__init__(base_url=base_url)
    
    async def health_check(self) -> bool:
        """健康检查"""
        response = await self.get("/studies", params={"pageSize": 1})
        return response.success
    
    async def search_studies(
        self,
        query: str | None = None,
        condition: str | None = None,
        intervention: str | None = None,
        sponsor: str | None = None,
        status: list[str] | None = None,
        phase: list[str] | None = None,
        page_size: int = 20,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """搜索临床试验
        
        Args:
            query: 全文搜索关键词
            condition: 适应症
            intervention: 干预措施/药物
            sponsor: 申办方
            status: 状态过滤
            phase: 阶段过滤
            page_size: 每页数量
            page_token: 分页令牌
            
        Returns:
            dict: 搜索结果
        """
        params = {
            "pageSize": page_size,
            "format": "json",
        }
        
        # 构建查询条件
        query_parts = []
        
        if query:
            query_parts.append(query)
        
        if condition:
            query_parts.append(f"AREA[Condition]{condition}")
        
        if intervention:
            query_parts.append(f"AREA[Intervention]{intervention}")
        
        if sponsor:
            query_parts.append(f"AREA[LeadSponsorName]{sponsor}")
        
        if query_parts:
            params["query.term"] = " AND ".join(query_parts)
        
        if status:
            params["filter.overallStatus"] = ",".join(status)
        
        if phase:
            params["filter.phase"] = ",".join(phase)
        
        if page_token:
            params["pageToken"] = page_token
        
        response = await self.get("/studies", params=params)
        
        if not response.success:
            logger.error(f"Search failed: {response.error}")
            return {"studies": [], "totalCount": 0}
        
        return response.data
    
    async def get_study(self, nct_id: str) -> ClinicalTrialStudy | None:
        """获取单个临床试验详情
        
        Args:
            nct_id: NCT 编号
            
        Returns:
            ClinicalTrialStudy | None: 试验详情
        """
        response = await self.get(f"/studies/{nct_id}")
        
        if not response.success:
            logger.error(f"Failed to get study {nct_id}: {response.error}")
            return None
        
        study_data = response.data
        
        # 解析响应
        protocol = study_data.get("protocolSection", {})
        id_module = protocol.get("identificationModule", {})
        status_module = protocol.get("statusModule", {})
        design_module = protocol.get("designModule", {})
        conditions_module = protocol.get("conditionsModule", {})
        interventions_module = protocol.get("armsInterventionsModule", {})
        sponsors_module = protocol.get("sponsorCollaboratorsModule", {})
        outcomes_module = protocol.get("outcomesModule", {})
        
        return ClinicalTrialStudy(
            nct_id=nct_id,
            title=id_module.get("officialTitle", id_module.get("briefTitle", "")),
            status=status_module.get("overallStatus", ""),
            phase=design_module.get("phases", [None])[0] if design_module.get("phases") else None,
            enrollment=design_module.get("enrollmentInfo", {}).get("count"),
            start_date=status_module.get("startDateStruct", {}).get("date"),
            completion_date=status_module.get("completionDateStruct", {}).get("date"),
            conditions=conditions_module.get("conditions", []),
            interventions=interventions_module.get("interventions", []),
            sponsors=[sponsors_module.get("leadSponsor", {})] if sponsors_module.get("leadSponsor") else [],
            design=design_module,
            outcomes=outcomes_module.get("primaryOutcomes", []),
        )
    
    async def search_by_drug(
        self,
        drug_name: str,
        status: list[str] | None = None,
        phase: list[str] | None = None,
        page_size: int = 50,
    ) -> list[ClinicalTrialStudy]:
        """按药物名称搜索临床试验
        
        Args:
            drug_name: 药物名称
            status: 状态过滤
            phase: 阶段过滤
            page_size: 每页数量
            
        Returns:
            list[ClinicalTrialStudy]: 试验列表
        """
        result = await self.search_studies(
            intervention=drug_name,
            status=status,
            phase=phase,
            page_size=page_size,
        )
        
        studies = []
        for study_data in result.get("studies", []):
            protocol = study_data.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})
            status_module = protocol.get("statusModule", {})
            design_module = protocol.get("designModule", {})
            
            nct_id = id_module.get("nctId", "")
            if nct_id:
                study = ClinicalTrialStudy(
                    nct_id=nct_id,
                    title=id_module.get("officialTitle", id_module.get("briefTitle", "")),
                    status=status_module.get("overallStatus", ""),
                    phase=design_module.get("phases", [None])[0] if design_module.get("phases") else None,
                    enrollment=design_module.get("enrollmentInfo", {}).get("count"),
                )
                studies.append(study)
        
        return studies
    
    def convert_to_trial_node(self, study: ClinicalTrialStudy) -> Trial:
        """将 API 数据转换为 Trial 节点
        
        Args:
            study: API 返回的试验数据
            
        Returns:
            Trial: Trial 节点对象
        """
        # 状态映射
        status_map = {
            "RECRUITING": TrialStatus.RECRUITING,
            "ACTIVE_NOT_RECRUITING": TrialStatus.ACTIVE_NOT_RECRUITING,
            "COMPLETED": TrialStatus.COMPLETED,
            "SUSPENDED": TrialStatus.SUSPENDED,
            "TERMINATED": TrialStatus.TERMINATED,
            "WITHDRAWN": TrialStatus.WITHDRAWN,
            "NOT_YET_RECRUITING": TrialStatus.NOT_YET_RECRUITING,
        }
        
        # 阶段映射
        phase_map = {
            "PHASE1": TrialPhase.PHASE_1,
            "PHASE2": TrialPhase.PHASE_2,
            "PHASE3": TrialPhase.PHASE_3,
            "PHASE4": TrialPhase.PHASE_4,
            "EARLY_PHASE1": TrialPhase.PHASE_1,
            "NA": TrialPhase.PRECLINICAL,
        }
        
        # 设计映射
        design_info = study.design
        design_type = design_info.get("designInfo", {}).get("allocation", "")
        
        design_map = {
            "RANDOMIZED": TrialDesign.DOUBLE_BLIND,
            "NON_RANDOMIZED": TrialDesign.OPEN_LABEL,
            "NA": TrialDesign.SINGLE_ARM,
        }
        
        return Trial(
            nct_id=study.nct_id,
            title=study.title,
            design=design_map.get(design_type, TrialDesign.OPEN_LABEL),
            phase=phase_map.get(study.phase, TrialPhase.PHASE_2) if study.phase else TrialPhase.PHASE_2,
            status=status_map.get(study.status, TrialStatus.RECRUITING),
            enrollment_target=study.enrollment,
            sponsor=study.sponsors[0].get("name") if study.sponsors else None,
        )

