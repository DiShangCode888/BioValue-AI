# 数据诚信检查
"""
数据诚信预警:
如果终点数据的p值极其显著，但KM曲线在尾部有大量删失点，
图谱会自动触发"数据可靠性存疑"标签。
"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import Any

from src.knowledge import get_neo4j_client
from src.knowledge.queries import DATA_INTEGRITY_CHECK_QUERY, SUSPICIOUS_DATA_QUERY
from src.llms import get_llm
from src.utils import get_logger

logger = get_logger(__name__)


class RiskLevel(str, Enum):
    """风险等级"""
    LOW = "LOW_RISK"
    MEDIUM = "MEDIUM_RISK"
    HIGH = "HIGH_RISK"
    CRITICAL = "CRITICAL_RISK"


class SuspiciousDataPoint(BaseModel):
    """可疑数据点"""
    trial_nct: str
    trial_title: str | None = None
    trial_phase: str | None = None
    company: str | None = None
    
    # 终点数据
    mpfs_months: float | None = None
    mos_months: float | None = None
    orr_percent: float | None = None
    hr_pfs: float | None = None
    hr_pfs_p_value: float | None = None
    hr_os: float | None = None
    hr_os_p_value: float | None = None
    grade3_plus_ae_rate: float | None = None
    
    # 数据质量指标
    censoring_density: float | None = None
    tail_effect_strength: float | None = None
    
    # 风险评估
    risk_level: RiskLevel = RiskLevel.LOW
    concerns: list[str] = Field(default_factory=list)
    km_asset_url: str | None = None


class IntegrityCheckResult(BaseModel):
    """数据诚信检查结果"""
    total_checked: int = 0
    suspicious_count: int = 0
    critical_count: int = 0
    high_risk_count: int = 0
    medium_risk_count: int = 0
    suspicious_data: list[SuspiciousDataPoint] = Field(default_factory=list)
    summary: str = ""
    recommendations: list[str] = Field(default_factory=list)


class DataIntegrityChecker:
    """数据诚信检查器
    
    识别可疑的临床数据:
    1. p值极显著但HR接近1
    2. 高删失点密度
    3. 统计学结果与临床意义不匹配
    """
    
    def __init__(self):
        self._client = get_neo4j_client()
    
    async def check_integrity(
        self,
        p_value_threshold: float = 0.05,
        censoring_threshold: float = 0.5,
        include_llm_analysis: bool = True,
    ) -> IntegrityCheckResult:
        """执行数据诚信检查
        
        Args:
            p_value_threshold: p值阈值
            censoring_threshold: 删失密度阈值
            include_llm_analysis: 是否包含 LLM 分析
            
        Returns:
            IntegrityCheckResult: 检查结果
        """
        logger.info(f"Checking data integrity with p<{p_value_threshold}, "
                   f"censoring>{censoring_threshold}")
        
        await self._client.connect()
        
        # 执行图谱查询
        query_results = await self._client.execute_query(
            DATA_INTEGRITY_CHECK_QUERY,
            {
                "p_value_threshold": p_value_threshold,
                "censoring_threshold": censoring_threshold,
            }
        )
        
        # 解析结果
        suspicious_data = []
        critical_count = 0
        high_risk_count = 0
        medium_risk_count = 0
        
        for result in query_results:
            check = result.get("integrity_check", {})
            trial_info = check.get("trial", {})
            endpoint_info = check.get("endpoint", {})
            quality_info = check.get("data_quality", {})
            warning_level = check.get("warning_level", "LOW_RISK")
            
            # 生成关注点列表
            concerns = self._identify_concerns(endpoint_info, quality_info)
            
            data_point = SuspiciousDataPoint(
                trial_nct=trial_info.get("nct_id", ""),
                trial_title=trial_info.get("title"),
                trial_phase=trial_info.get("phase"),
                mpfs_months=endpoint_info.get("mpfs_months"),
                mos_months=endpoint_info.get("mos_months"),
                orr_percent=endpoint_info.get("orr_percent"),
                hr_pfs=endpoint_info.get("hr_pfs"),
                hr_pfs_p_value=endpoint_info.get("hr_pfs_p_value"),
                hr_os=endpoint_info.get("hr_os"),
                hr_os_p_value=endpoint_info.get("hr_os_p_value"),
                grade3_plus_ae_rate=endpoint_info.get("grade3_plus_ae_rate"),
                censoring_density=quality_info.get("censoring_density"),
                tail_effect_strength=quality_info.get("tail_effect"),
                risk_level=RiskLevel(warning_level),
                concerns=concerns,
                km_asset_url=check.get("km_asset"),
            )
            
            suspicious_data.append(data_point)
            
            if warning_level == "CRITICAL_RISK":
                critical_count += 1
            elif warning_level == "HIGH_RISK":
                high_risk_count += 1
            elif warning_level == "MEDIUM_RISK":
                medium_risk_count += 1
        
        result = IntegrityCheckResult(
            total_checked=len(query_results),
            suspicious_count=len(suspicious_data),
            critical_count=critical_count,
            high_risk_count=high_risk_count,
            medium_risk_count=medium_risk_count,
            suspicious_data=suspicious_data,
        )
        
        # LLM 分析
        if include_llm_analysis and suspicious_data:
            summary, recommendations = await self._llm_analyze(result)
            result.summary = summary
            result.recommendations = recommendations
        
        return result
    
    async def find_suspicious_patterns(self) -> list[dict[str, Any]]:
        """查找统计学结果与临床意义不匹配的数据
        
        Returns:
            list[dict]: 可疑数据模式
        """
        await self._client.connect()
        
        results = await self._client.execute_query(SUSPICIOUS_DATA_QUERY, {})
        return results
    
    def _identify_concerns(
        self,
        endpoint: dict,
        quality: dict
    ) -> list[str]:
        """识别数据关注点"""
        concerns = []
        
        # 检查HR与p值不匹配
        hr_pfs = endpoint.get("hr_pfs")
        hr_pfs_p = endpoint.get("hr_pfs_p_value")
        if hr_pfs and hr_pfs_p:
            if hr_pfs > 0.85 and hr_pfs_p < 0.01:
                concerns.append("HR接近1但p值极显著，可能存在样本量过大导致的统计学假阳性")
        
        hr_os = endpoint.get("hr_os")
        hr_os_p = endpoint.get("hr_os_p_value")
        if hr_os and hr_os_p:
            if hr_os > 0.85 and hr_os_p < 0.01:
                concerns.append("OS的HR接近1但p值显著，需审查数据成熟度")
        
        # 检查高删失点密度
        censoring = quality.get("censoring_density")
        if censoring and censoring > 0.7:
            concerns.append(f"删失点密度过高({censoring:.2f})，KM曲线尾部可靠性存疑")
        elif censoring and censoring > 0.5:
            concerns.append(f"删失点密度偏高({censoring:.2f})，建议关注长期随访数据")
        
        # 检查疗效与毒性不平衡
        orr = endpoint.get("orr_percent")
        ae_rate = endpoint.get("grade3_plus_ae_rate")
        if orr and ae_rate:
            if orr > 80 and ae_rate > 60:
                concerns.append("高缓解率伴随高毒性，需仔细评估风险收益比")
        
        # 检查拖尾效应
        tail_effect = quality.get("tail_effect")
        if tail_effect and tail_effect < 0.2 and endpoint.get("mpfs_months", 0) > 12:
            concerns.append("长mPFS但无明显拖尾效应，可能非免疫治疗特征")
        
        return concerns
    
    async def _llm_analyze(
        self,
        result: IntegrityCheckResult
    ) -> tuple[str, list[str]]:
        """使用 LLM 进行深度分析"""
        llm = get_llm("reasoning")
        
        prompt = f"""请分析以下数据诚信检查结果，并给出投资建议:

检查总数: {result.total_checked}
可疑数据数: {result.suspicious_count}
- 严重风险: {result.critical_count} 个
- 高风险: {result.high_risk_count} 个
- 中风险: {result.medium_risk_count} 个

高风险数据详情:
"""
        for data in result.suspicious_data[:5]:
            if data.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
                prompt += f"""
- 试验: {data.trial_nct} ({data.trial_phase or 'N/A'})
  - HR(PFS): {data.hr_pfs or 'N/A'}, p值: {data.hr_pfs_p_value or 'N/A'}
  - 删失密度: {data.censoring_density or 'N/A'}
  - 关注点: {'; '.join(data.concerns) if data.concerns else 'N/A'}
"""
        
        prompt += """
请从以下角度分析:
1. 数据可靠性整体评估
2. 需要特别警惕的试验
3. 对投资决策的影响
4. 建议的后续行动
"""
        
        response = await llm.generate(
            prompt=prompt,
            system_prompt="你是一位临床数据审计专家，专注于识别临床试验数据中的潜在问题和统计学陷阱。",
        )
        
        # 提取建议
        recommendations = []
        lines = response.content.split("\n")
        
        for line in lines:
            if "建议" in line or "行动" in line:
                continue
            if line.strip().startswith(("-", "•", "*", "1", "2", "3")):
                rec = line.strip().lstrip("-•*0123456789. ")
                if rec and len(rec) > 10:
                    recommendations.append(rec)
        
        return response.content, recommendations[:5]

