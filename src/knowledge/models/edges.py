# 知识图谱关联模型
"""
定义创新药知识图谱的核心关联类型:

1. TREATS: [药物] --(TREATS)--> [适应症]
2. OUTPUTS: [临床实验] --(OUTPUTS)--> [终点数据]
3. COMBINED_WITH: [药物A] --(COMBINED_WITH)--> [药物B]
4. HAS_SOC: [适应症] --(HAS_SOC)--> [药物X]
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def generate_id() -> str:
    """生成唯一ID"""
    return str(uuid4())


class EdgeType(str, Enum):
    """边类型枚举"""
    TREATS = "TREATS"
    OUTPUTS = "OUTPUTS"
    COMBINED_WITH = "COMBINED_WITH"
    HAS_SOC = "HAS_SOC"
    DEVELOPED_BY = "DEVELOPED_BY"
    CONDUCTS = "CONDUCTS"
    HAS_ASSET = "HAS_ASSET"
    HAS_FACTOR = "HAS_FACTOR"
    PART_OF_COMBO = "PART_OF_COMBO"
    HAS_LANDMARK = "HAS_LANDMARK"


class BaseEdge(BaseModel):
    """边基类"""
    id: str = Field(default_factory=generate_id)
    edge_type: EdgeType
    source_id: str = Field(..., description="源节点ID")
    target_id: str = Field(..., description="目标节点ID")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def to_neo4j_properties(self) -> dict:
        """转换为 Neo4j 属性字典"""
        data = self.model_dump(exclude={"edge_type", "source_id", "target_id"})
        # 转换日期时间
        for key, value in data.items():
            if isinstance(value, (datetime, date)):
                data[key] = value.isoformat()
            elif isinstance(value, Enum):
                data[key] = value.value
        return data


class TreatsRelation(BaseEdge):
    """[药物] --(TREATS)--> [适应症]
    
    属性:
    - 治疗线数
    - 当前优先级
    - 市场预计渗透率
    """
    edge_type: EdgeType = EdgeType.TREATS
    
    # 治疗线数
    treatment_line: Optional[str] = Field(None, description="治疗线数(1L/2L/3L+)")
    
    # 优先级
    priority: Optional[int] = Field(
        None, ge=1, le=10, description="当前开发优先级(1-10, 10最高)"
    )
    
    # 市场预计
    market_penetration_estimate: Optional[float] = Field(
        None, ge=0, le=1, description="市场预计渗透率(0-1)"
    )
    peak_sales_estimate: Optional[float] = Field(
        None, description="峰值销售额预估(亿美元)"
    )
    
    # 审批状态
    approval_status: Optional[str] = Field(None, description="该适应症审批状态")
    approval_date: Optional[date] = Field(None, description="获批日期")
    
    # 临床阶段
    development_stage: Optional[str] = Field(None, description="开发阶段")
    is_primary_indication: bool = Field(False, description="是否主要适应症")


class OutputsRelation(BaseEdge):
    """[临床实验] --(OUTPUTS)--> [终点数据]
    
    属性:
    - 数据发布日期
    - 实验阶段
    - 拖尾效应强度 (0-1)
    - 删失点密集度评分
    """
    edge_type: EdgeType = EdgeType.OUTPUTS
    
    # 数据发布信息
    publication_date: Optional[date] = Field(None, description="数据发布日期")
    publication_venue: Optional[str] = Field(None, description="发布场合(会议/期刊)")
    
    # 实验阶段
    trial_phase: Optional[str] = Field(None, description="实验阶段")
    is_primary_analysis: bool = Field(True, description="是否主要分析")
    analysis_type: Optional[str] = Field(None, description="分析类型(期中/最终)")
    
    # 拖尾效应评估
    tail_effect_strength: Optional[float] = Field(
        None, ge=0, le=1, description="拖尾效应强度(0-1)"
    )
    censoring_density_score: Optional[float] = Field(
        None, ge=0, le=1, description="删失点密集度评分(0-1, 越低越好)"
    )
    
    # 数据质量
    data_quality_score: Optional[float] = Field(
        None, ge=0, le=10, description="数据质量评分(0-10)"
    )
    data_reliability_flag: Optional[str] = Field(
        None, description="数据可靠性标记(可靠/存疑/不可靠)"
    )


class CombinedWithRelation(BaseEdge):
    """[药物A] --(COMBINED_WITH)--> [药物B]
    
    属性:
    - 协同效应评分
    - 联合用药的实验结果链接
    """
    edge_type: EdgeType = EdgeType.COMBINED_WITH
    
    # 协同效应
    synergy_score: Optional[float] = Field(
        None, ge=0, le=10, description="协同效应评分(0-10)"
    )
    synergy_type: Optional[str] = Field(
        None, description="协同类型(增效/减毒/互补)"
    )
    synergy_mechanism: Optional[str] = Field(
        None, description="协同机制描述"
    )
    
    # 联合用药实验
    combo_trial_nct_ids: list[str] = Field(
        default_factory=list, description="联合用药实验NCT编号列表"
    )
    combo_trial_results_url: Optional[str] = Field(
        None, description="实验结果链接"
    )
    
    # 临床数据
    combo_orr: Optional[float] = Field(
        None, ge=0, le=100, description="联合用药ORR(%)"
    )
    combo_mpfs: Optional[float] = Field(
        None, description="联合用药mPFS(月)"
    )
    monotherapy_comparison: Optional[str] = Field(
        None, description="与单药对比结论"
    )
    
    # 安全性
    combo_safety_profile: Optional[str] = Field(
        None, description="联合用药安全性描述"
    )
    additional_toxicity: Optional[str] = Field(
        None, description="额外毒性"
    )


class HasSocRelation(BaseEdge):
    """[适应症] --(HAS_SOC)--> [药物X]
    
    属性:
    - 纳入基准时间 (用于判断其他药物是否在挑战过时的标准)
    """
    edge_type: EdgeType = EdgeType.HAS_SOC
    
    # 纳入时间
    soc_established_date: Optional[date] = Field(
        None, description="确立为标准疗法的日期"
    )
    guideline_source: Optional[str] = Field(
        None, description="指南来源(NCCN/CSCO等)"
    )
    guideline_version: Optional[str] = Field(
        None, description="指南版本"
    )
    
    # SoC评估
    is_current_soc: bool = Field(True, description="是否为当前SoC")
    soc_efficacy_benchmark: Optional[str] = Field(
        None, description="疗效基准(mPFS/mOS等)"
    )
    
    # 挑战评估
    years_as_soc: Optional[int] = Field(
        None, description="作为SoC的年数"
    )
    is_being_challenged: bool = Field(False, description="是否正在被挑战")
    challenging_drugs: list[str] = Field(
        default_factory=list, description="正在挑战的药物列表"
    )
    
    # 市场地位
    market_share: Optional[float] = Field(
        None, ge=0, le=1, description="市场份额"
    )
    replacement_risk_score: Optional[float] = Field(
        None, ge=0, le=10, description="被替代风险评分(0-10)"
    )


# 辅助关系类型

class DevelopedByRelation(BaseEdge):
    """[药物] --(DEVELOPED_BY)--> [公司]"""
    edge_type: EdgeType = EdgeType.DEVELOPED_BY
    
    role: Optional[str] = Field(None, description="角色(原研/授权/合作)")
    license_date: Optional[date] = Field(None, description="授权日期")
    territory: Optional[str] = Field(None, description="授权区域")


class ConductsRelation(BaseEdge):
    """[公司] --(CONDUCTS)--> [临床实验]"""
    edge_type: EdgeType = EdgeType.CONDUCTS
    
    role: Optional[str] = Field(None, description="角色(申办方/合作方)")


class HasAssetRelation(BaseEdge):
    """[实体] --(HAS_ASSET)--> [媒体资源]"""
    edge_type: EdgeType = EdgeType.HAS_ASSET
    
    asset_category: Optional[str] = Field(None, description="资源类别")


class HasFactorRelation(BaseEdge):
    """[实体] --(HAS_FACTOR)--> [外部因素]"""
    edge_type: EdgeType = EdgeType.HAS_FACTOR
    
    factor_category: Optional[str] = Field(None, description="因素类别")


class PartOfComboRelation(BaseEdge):
    """[药物] --(PART_OF_COMBO)--> [联合方案节点]"""
    edge_type: EdgeType = EdgeType.PART_OF_COMBO
    
    role_in_combo: Optional[str] = Field(None, description="在联合方案中的角色")


class HasLandmarkRelation(BaseEdge):
    """[终点数据] --(HAS_LANDMARK)--> [里程碑数据点]"""
    edge_type: EdgeType = EdgeType.HAS_LANDMARK
    
    endpoint_type: Optional[str] = Field(None, description="终点类型")

