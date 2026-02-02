# 知识图谱节点模型
"""
定义创新药知识图谱的核心节点类型:

1. Company (公司) - 制药企业信息
2. Drug (药物) - 药物核心属性
3. Indication (适应症) - 疾病/治疗领域
4. Trial (临床实验) - 临床试验信息
5. EndpointData (终点数据) - 临床疗效数据
6. MediaAsset (媒体资源) - 相关文档资源
7. ExternalFactor (外部因素) - 政策/市场因素
8. ComboNode (联合方案节点) - 联合用药虚拟节点
9. LandmarkNode (里程碑数据点) - 长期生存率数据
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def generate_id() -> str:
    """生成唯一ID"""
    return str(uuid4())


class NodeType(str, Enum):
    """节点类型枚举"""
    COMPANY = "Company"
    DRUG = "Drug"
    INDICATION = "Indication"
    TRIAL = "Trial"
    ENDPOINT_DATA = "EndpointData"
    MEDIA_ASSET = "MediaAsset"
    EXTERNAL_FACTOR = "ExternalFactor"
    COMBO_NODE = "ComboNode"
    LANDMARK_NODE = "LandmarkNode"


class MoleculeType(str, Enum):
    """分子类型枚举"""
    ADC = "ADC"  # 抗体药物偶联物
    MONOCLONAL = "单抗"  # 单克隆抗体
    BISPECIFIC = "双抗"  # 双特异性抗体
    SMALL_MOLECULE = "小分子"
    CAR_T = "CAR-T"
    MRNA = "mRNA"
    GENE_THERAPY = "基因疗法"
    CELL_THERAPY = "细胞疗法"
    OTHER = "其他"


class TrialDesign(str, Enum):
    """实验设计枚举"""
    DOUBLE_BLIND = "双盲"
    SINGLE_ARM = "单臂"
    OPEN_LABEL = "开放标签"
    CROSSOVER = "交叉"
    BASKET = "篮式设计"
    UMBRELLA = "伞式设计"
    ADAPTIVE = "适应性设计"


class TrialPhase(str, Enum):
    """临床阶段枚举"""
    PRECLINICAL = "临床前"
    PHASE_1 = "Phase I"
    PHASE_1_2 = "Phase I/II"
    PHASE_2 = "Phase II"
    PHASE_2_3 = "Phase II/III"
    PHASE_3 = "Phase III"
    PHASE_4 = "Phase IV"
    APPROVED = "已获批"


class TreatmentLine(str, Enum):
    """治疗线数枚举"""
    FIRST_LINE = "1L"
    SECOND_LINE = "2L"
    THIRD_LINE_PLUS = "3L+"
    ADJUVANT = "辅助治疗"
    NEOADJUVANT = "新辅助治疗"
    MAINTENANCE = "维持治疗"


class TrialStatus(str, Enum):
    """临床实验状态"""
    NOT_YET_RECRUITING = "尚未招募"
    RECRUITING = "招募中"
    ACTIVE_NOT_RECRUITING = "进行中-不招募"
    COMPLETED = "已完成"
    SUSPENDED = "暂停"
    TERMINATED = "终止"
    WITHDRAWN = "撤回"


class BaseNode(BaseModel):
    """节点基类"""
    id: str = Field(default_factory=generate_id)
    node_type: NodeType
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def to_neo4j_properties(self) -> dict:
        """转换为 Neo4j 属性字典"""
        data = self.model_dump(exclude={"node_type"})
        # 转换日期时间
        for key, value in data.items():
            if isinstance(value, (datetime, date)):
                data[key] = value.isoformat()
            elif isinstance(value, Enum):
                data[key] = value.value
        return data


class Company(BaseNode):
    """公司节点
    
    核心属性:
    - 现金余额 (Cash Run-rate)
    - 融资轮次
    - 研发费用占比
    - 核心科学家背景评分
    """
    node_type: NodeType = NodeType.COMPANY
    
    name: str = Field(..., description="公司名称")
    name_en: Optional[str] = Field(None, description="英文名称")
    stock_code: Optional[str] = Field(None, description="股票代码")
    
    # 财务指标
    cash_balance: Optional[float] = Field(None, description="现金余额(亿元)")
    cash_runway_months: Optional[int] = Field(None, description="现金可用月数")
    funding_round: Optional[str] = Field(None, description="融资轮次")
    total_funding: Optional[float] = Field(None, description="累计融资额(亿元)")
    
    # 研发指标
    rd_expense_ratio: Optional[float] = Field(None, ge=0, le=1, description="研发费用占比")
    pipeline_count: Optional[int] = Field(None, description="在研管线数量")
    
    # 团队评估
    scientist_background_score: Optional[float] = Field(
        None, ge=0, le=10, description="核心科学家背景评分(0-10)"
    )
    management_score: Optional[float] = Field(
        None, ge=0, le=10, description="管理团队评分(0-10)"
    )
    
    # 元信息
    founded_year: Optional[int] = Field(None, description="成立年份")
    headquarters: Optional[str] = Field(None, description="总部位置")
    employee_count: Optional[int] = Field(None, description="员工人数")


class Drug(BaseNode):
    """药物节点
    
    核心属性:
    - 分子类型 (ADC/单抗等)
    - 靶点
    - 作用机制 (MoA)
    - 专利失效日 (LOE)
    - 给药方式
    """
    node_type: NodeType = NodeType.DRUG
    
    name: str = Field(..., description="药物名称")
    name_en: Optional[str] = Field(None, description="英文名称")
    generic_name: Optional[str] = Field(None, description="通用名")
    brand_name: Optional[str] = Field(None, description="商品名")
    
    # 核心属性
    molecule_type: MoleculeType = Field(..., description="分子类型")
    target: str = Field(..., description="靶点")
    moa: str = Field(..., description="作用机制(Mechanism of Action)")
    
    # 专利信息
    loe_date: Optional[date] = Field(None, description="专利失效日(Loss of Exclusivity)")
    patent_numbers: list[str] = Field(default_factory=list, description="专利号列表")
    
    # 给药信息
    administration_route: Optional[str] = Field(None, description="给药途径")
    dosage_form: Optional[str] = Field(None, description="剂型")
    recommended_dose: Optional[str] = Field(None, description="推荐剂量")
    
    # 审批状态
    approval_status: Optional[str] = Field(None, description="审批状态")
    first_approval_date: Optional[date] = Field(None, description="首次获批日期")
    approved_regions: list[str] = Field(default_factory=list, description="获批地区")
    
    # 关联公司
    company_id: Optional[str] = Field(None, description="所属公司ID")
    originator: Optional[str] = Field(None, description="原研公司")
    licensee: Optional[str] = Field(None, description="授权方")


class Indication(BaseNode):
    """适应症节点
    
    核心属性:
    - 流行病学数据 (N)
    - 当前 SoC (标准疗法)
    - 未满足需求程度 (1-10评分)
    """
    node_type: NodeType = NodeType.INDICATION
    
    name: str = Field(..., description="适应症名称")
    name_en: Optional[str] = Field(None, description="英文名称")
    icd_code: Optional[str] = Field(None, description="ICD编码")
    
    # 流行病学数据
    prevalence: Optional[int] = Field(None, description="患病人数")
    incidence_annual: Optional[int] = Field(None, description="年新发病例数")
    prevalence_region: Optional[str] = Field(None, description="流行病学数据地区")
    
    # 治疗现状
    current_soc: Optional[str] = Field(None, description="当前标准疗法(SoC)")
    soc_efficacy_score: Optional[float] = Field(
        None, ge=0, le=10, description="现有疗法疗效评分(0-10)"
    )
    
    # 需求评估
    unmet_need_score: Optional[float] = Field(
        None, ge=0, le=10, description="未满足需求程度(0-10)"
    )
    unmet_need_description: Optional[str] = Field(None, description="未满足需求描述")
    
    # 市场信息
    market_size: Optional[float] = Field(None, description="市场规模(亿美元)")
    growth_rate: Optional[float] = Field(None, description="年增长率")
    
    # 分类信息
    therapeutic_area: Optional[str] = Field(None, description="治疗领域")
    disease_type: Optional[str] = Field(None, description="疾病类型")
    is_rare_disease: bool = Field(False, description="是否罕见病")


class Trial(BaseNode):
    """临床实验节点
    
    核心属性:
    - NCT编号
    - 实验设计 (双盲/单臂)
    - 入组人数 (N)
    - 治疗线数 (1L/2L/3L+)
    - 状态
    """
    node_type: NodeType = NodeType.TRIAL
    
    nct_id: str = Field(..., description="NCT编号")
    title: str = Field(..., description="实验标题")
    
    # 设计信息
    design: TrialDesign = Field(..., description="实验设计")
    phase: TrialPhase = Field(..., description="临床阶段")
    treatment_line: Optional[TreatmentLine] = Field(None, description="治疗线数")
    
    # 入组信息
    enrollment_target: Optional[int] = Field(None, description="计划入组人数")
    enrollment_actual: Optional[int] = Field(None, description="实际入组人数")
    
    # 状态信息
    status: TrialStatus = Field(..., description="实验状态")
    start_date: Optional[date] = Field(None, description="开始日期")
    completion_date: Optional[date] = Field(None, description="预计完成日期")
    actual_completion_date: Optional[date] = Field(None, description="实际完成日期")
    
    # 主要终点
    primary_endpoint: Optional[str] = Field(None, description="主要终点")
    secondary_endpoints: list[str] = Field(default_factory=list, description="次要终点")
    
    # 对照组
    comparator: Optional[str] = Field(None, description="对照组")
    is_placebo_controlled: bool = Field(False, description="是否安慰剂对照")
    
    # 关联信息
    drug_id: Optional[str] = Field(None, description="研究药物ID")
    indication_id: Optional[str] = Field(None, description="适应症ID")
    sponsor: Optional[str] = Field(None, description="申办方")


class EndpointData(BaseNode):
    """终点数据节点
    
    核心属性:
    - mPFS (中位无进展生存期)
    - mOS (中位总生存期)
    - ORR (客观缓解率)
    - HR值及95%CI
    - p值
    - G3+不良反应率
    """
    node_type: NodeType = NodeType.ENDPOINT_DATA
    
    trial_id: str = Field(..., description="关联临床实验ID")
    data_cutoff_date: Optional[date] = Field(None, description="数据截止日期")
    publication_date: Optional[date] = Field(None, description="数据发布日期")
    
    # 疗效数据
    mpfs_months: Optional[float] = Field(None, description="中位无进展生存期(月)")
    mpfs_ci_lower: Optional[float] = Field(None, description="mPFS 95%CI下限")
    mpfs_ci_upper: Optional[float] = Field(None, description="mPFS 95%CI上限")
    
    mos_months: Optional[float] = Field(None, description="中位总生存期(月)")
    mos_ci_lower: Optional[float] = Field(None, description="mOS 95%CI下限")
    mos_ci_upper: Optional[float] = Field(None, description="mOS 95%CI上限")
    
    orr_percent: Optional[float] = Field(None, ge=0, le=100, description="客观缓解率(%)")
    dcr_percent: Optional[float] = Field(None, ge=0, le=100, description="疾病控制率(%)")
    cr_percent: Optional[float] = Field(None, ge=0, le=100, description="完全缓解率(%)")
    
    # 风险比
    hr_pfs: Optional[float] = Field(None, description="PFS风险比(HR)")
    hr_pfs_ci_lower: Optional[float] = Field(None, description="HR(PFS) 95%CI下限")
    hr_pfs_ci_upper: Optional[float] = Field(None, description="HR(PFS) 95%CI上限")
    hr_pfs_p_value: Optional[float] = Field(None, description="HR(PFS) p值")
    
    hr_os: Optional[float] = Field(None, description="OS风险比(HR)")
    hr_os_ci_lower: Optional[float] = Field(None, description="HR(OS) 95%CI下限")
    hr_os_ci_upper: Optional[float] = Field(None, description="HR(OS) 95%CI上限")
    hr_os_p_value: Optional[float] = Field(None, description="HR(OS) p值")
    
    # 安全性数据
    grade3_plus_ae_rate: Optional[float] = Field(
        None, ge=0, le=100, description="3级以上不良反应率(%)"
    )
    sae_rate: Optional[float] = Field(None, ge=0, le=100, description="严重不良反应率(%)")
    discontinuation_rate: Optional[float] = Field(
        None, ge=0, le=100, description="因不良反应停药率(%)"
    )
    treatment_related_death: Optional[int] = Field(None, description="治疗相关死亡人数")
    
    # 拖尾效应评估
    tail_effect_strength: Optional[float] = Field(
        None, ge=0, le=1, description="拖尾效应强度(0-1)"
    )
    censoring_density_score: Optional[float] = Field(
        None, ge=0, le=1, description="删失点密集度评分(0-1)"
    )
    
    # 数据可靠性
    data_maturity: Optional[str] = Field(None, description="数据成熟度")
    follow_up_months: Optional[float] = Field(None, description="中位随访时间(月)")


class MediaAsset(BaseNode):
    """媒体资源节点
    
    核心属性:
    - KM曲线图片地址 (URL)
    - 原始财报PDF地址
    - FDA审议函文本链接
    """
    node_type: NodeType = NodeType.MEDIA_ASSET
    
    asset_type: str = Field(..., description="资源类型")
    title: str = Field(..., description="资源标题")
    
    # URL
    url: str = Field(..., description="资源URL")
    local_path: Optional[str] = Field(None, description="本地存储路径")
    
    # 关联信息
    related_entity_id: Optional[str] = Field(None, description="关联实体ID")
    related_entity_type: Optional[str] = Field(None, description="关联实体类型")
    
    # 元信息
    file_type: Optional[str] = Field(None, description="文件类型")
    file_size: Optional[int] = Field(None, description="文件大小(bytes)")
    source: Optional[str] = Field(None, description="来源")
    publish_date: Optional[date] = Field(None, description="发布日期")
    
    # KM曲线特有属性
    km_coordinates: Optional[list[dict]] = Field(
        None, description="KM曲线坐标序列(由多模态模型提取)"
    )
    km_analysis_result: Optional[dict] = Field(
        None, description="KM曲线分析结果"
    )


class ExternalFactor(BaseNode):
    """外部因素节点
    
    核心属性:
    - 医保谈判状态
    - 集采压力评分
    - KOL正面/负面评价指数
    """
    node_type: NodeType = NodeType.EXTERNAL_FACTOR
    
    factor_type: str = Field(..., description="因素类型")
    related_entity_id: str = Field(..., description="关联实体ID")
    
    # 医保相关
    nrdl_status: Optional[str] = Field(None, description="国家医保目录状态")
    nrdl_entry_date: Optional[date] = Field(None, description="医保纳入日期")
    reimbursement_rate: Optional[float] = Field(None, ge=0, le=1, description="报销比例")
    
    # 集采相关
    vbp_pressure_score: Optional[float] = Field(
        None, ge=0, le=10, description="集采压力评分(0-10)"
    )
    vbp_round: Optional[str] = Field(None, description="集采批次")
    price_reduction_estimate: Optional[float] = Field(
        None, ge=0, le=1, description="预估降价幅度"
    )
    
    # KOL评价
    kol_positive_index: Optional[float] = Field(
        None, ge=0, le=10, description="KOL正面评价指数(0-10)"
    )
    kol_negative_index: Optional[float] = Field(
        None, ge=0, le=10, description="KOL负面评价指数(0-10)"
    )
    sentiment_score: Optional[float] = Field(
        None, ge=-1, le=1, description="综合情感得分(-1到1)"
    )
    
    # 监管相关
    regulatory_status: Optional[str] = Field(None, description="监管状态")
    fda_designation: Optional[str] = Field(None, description="FDA特殊认定")
    
    # 竞争环境
    competitive_intensity: Optional[float] = Field(
        None, ge=0, le=10, description="竞争激烈程度(0-10)"
    )
    market_share_estimate: Optional[float] = Field(
        None, ge=0, le=1, description="预估市场份额"
    )


class ComboNode(BaseNode):
    """联合方案节点 (虚拟聚合节点)
    
    当药物A和B联合时，产生一个虚拟节点。
    用于对比"A+B"与"A单药"或"SoC"的曲线差异。
    """
    node_type: NodeType = NodeType.COMBO_NODE
    
    name: str = Field(..., description="联合方案名称")
    drug_ids: list[str] = Field(..., min_length=2, description="组成药物ID列表")
    
    # 协同效应评估
    synergy_score: Optional[float] = Field(
        None, ge=0, le=10, description="协同效应评分(0-10)"
    )
    synergy_mechanism: Optional[str] = Field(None, description="协同机制描述")
    
    # 对比数据
    vs_monotherapy_benefit: Optional[str] = Field(None, description="相比单药优势")
    vs_soc_benefit: Optional[str] = Field(None, description="相比SoC优势")
    
    # 关联实验
    combo_trial_ids: list[str] = Field(default_factory=list, description="联合用药实验ID")


class LandmarkNode(BaseNode):
    """里程碑数据点节点
    
    在终点数据中，强制挂载 12个月、24个月、36个月生存率。
    这是捕捉免疫治疗"拖尾效应"的物理证据。
    """
    node_type: NodeType = NodeType.LANDMARK_NODE
    
    endpoint_data_id: str = Field(..., description="关联终点数据ID")
    endpoint_type: str = Field(..., description="终点类型(PFS/OS)")
    
    # 里程碑生存率
    month_12_rate: Optional[float] = Field(None, ge=0, le=1, description="12个月生存率")
    month_24_rate: Optional[float] = Field(None, ge=0, le=1, description="24个月生存率")
    month_36_rate: Optional[float] = Field(None, ge=0, le=1, description="36个月生存率")
    month_48_rate: Optional[float] = Field(None, ge=0, le=1, description="48个月生存率")
    month_60_rate: Optional[float] = Field(None, ge=0, le=1, description="60个月(5年)生存率")
    
    # 拖尾效应分析
    plateau_detected: bool = Field(False, description="是否检测到平台期")
    plateau_start_month: Optional[int] = Field(None, description="平台期开始月份")
    plateau_rate: Optional[float] = Field(None, ge=0, le=1, description="平台期生存率")
    
    # 数据质量
    patients_at_risk_12m: Optional[int] = Field(None, description="12个月风险人数")
    patients_at_risk_24m: Optional[int] = Field(None, description="24个月风险人数")
    patients_at_risk_36m: Optional[int] = Field(None, description="36个月风险人数")

