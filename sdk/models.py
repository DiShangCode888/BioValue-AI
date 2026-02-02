# SDK 数据模型
"""
BioValue-AI SDK 数据模型定义
"""

from datetime import date, datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ==================== 节点模型 ====================

class Drug(BaseModel):
    """药物"""
    id: str
    name: str
    name_en: Optional[str] = None
    molecule_type: str
    target: str
    moa: str
    loe_date: Optional[str] = None
    administration_route: Optional[str] = None
    approval_status: Optional[str] = None
    company_id: Optional[str] = None


class Company(BaseModel):
    """公司"""
    id: str
    name: str
    name_en: Optional[str] = None
    stock_code: Optional[str] = None
    cash_balance: Optional[float] = None
    funding_round: Optional[str] = None
    rd_expense_ratio: Optional[float] = None
    scientist_background_score: Optional[float] = None
    pipeline_count: Optional[int] = None


class Indication(BaseModel):
    """适应症"""
    id: str
    name: str
    name_en: Optional[str] = None
    prevalence: Optional[int] = None
    incidence_annual: Optional[int] = None
    current_soc: Optional[str] = None
    soc_efficacy_score: Optional[float] = None
    unmet_need_score: Optional[float] = None
    market_size: Optional[float] = None
    therapeutic_area: Optional[str] = None


class Trial(BaseModel):
    """临床试验"""
    id: str
    nct_id: str
    title: str
    design: str
    phase: str
    status: str
    treatment_line: Optional[str] = None
    enrollment_target: Optional[int] = None
    enrollment_actual: Optional[int] = None
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    primary_endpoint: Optional[str] = None
    drug_id: Optional[str] = None
    indication_id: Optional[str] = None


class EndpointData(BaseModel):
    """终点数据"""
    id: str
    trial_id: str
    mpfs_months: Optional[float] = None
    mos_months: Optional[float] = None
    orr_percent: Optional[float] = None
    hr_pfs: Optional[float] = None
    hr_pfs_p_value: Optional[float] = None
    hr_os: Optional[float] = None
    hr_os_p_value: Optional[float] = None
    grade3_plus_ae_rate: Optional[float] = None
    tail_effect_strength: Optional[float] = None


# ==================== 分析结果模型 ====================

class AffectedCombo(BaseModel):
    """受影响的联合用药"""
    partner_drug_id: str
    partner_drug_name: str
    synergy_score: Optional[float] = None
    company: Optional[str] = None
    treatment_line: Optional[str] = None
    trial_nct: Optional[str] = None
    trial_phase: Optional[str] = None
    adjusted_success_rate: Optional[float] = None


class CompetitionAnalysisResult(BaseModel):
    """竞争坍缩分析结果"""
    failed_drug_name: str
    failed_indication_id: str
    impact_severity: str
    total_affected_drugs: int
    total_affected_trials: int
    total_affected_companies: int
    affected_combinations: list[AffectedCombo] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    analysis: str = ""


class OpportunityIndication(BaseModel):
    """投资机会适应症"""
    indication_id: str
    indication_name: str
    prevalence: Optional[int] = None
    unmet_need_score: Optional[float] = None
    soc_efficacy_score: Optional[float] = None
    current_soc: Optional[str] = None
    market_size: Optional[float] = None
    investment_score: float = 0


class OpportunityResult(BaseModel):
    """空白点挖掘结果"""
    total_opportunities: int
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int
    high_priority: list[OpportunityIndication] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    analysis_summary: str = ""


class SuspiciousData(BaseModel):
    """可疑数据"""
    trial_nct: str
    trial_phase: Optional[str] = None
    hr_pfs: Optional[float] = None
    hr_pfs_p_value: Optional[float] = None
    censoring_density: Optional[float] = None
    risk_level: str
    concerns: list[str] = Field(default_factory=list)


class IntegrityCheckResult(BaseModel):
    """数据诚信检查结果"""
    total_checked: int
    suspicious_count: int
    critical_count: int
    high_risk_count: int
    medium_risk_count: int
    suspicious_data: list[SuspiciousData] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    summary: str = ""


# ==================== 工作流模型 ====================

class WorkflowResult(BaseModel):
    """工作流结果"""
    session_id: str
    query: str
    final_report: str
    summary: str
    completed_tasks_count: int = 0
    analysis_results_count: int = 0
    extracted_entities_count: int = 0
    created_nodes_count: int = 0


class ChatResponse(BaseModel):
    """对话响应"""
    session_id: str
    message: str
    response: str


# ==================== 通用模型 ====================

class GraphStatistics(BaseModel):
    """图谱统计"""
    nodes: dict[str, int]
    edges: dict[str, int]


class QueryResult(BaseModel):
    """查询结果"""
    results: list[dict[str, Any]]
    count: int

