# 分析路由
"""
投资分析 API
"""

from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.analysis import (
    CompetitionAnalyzer,
    OpportunityAnalyzer,
    DataIntegrityChecker,
)
from src.utils import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ==================== 请求/响应模型 ====================

class CompetitionAnalysisRequest(BaseModel):
    """竞争坍缩分析请求"""
    failed_drug_id: str
    failed_indication_id: str
    include_llm_analysis: bool = True


class CompetitionAnalysisResponse(BaseModel):
    """竞争坍缩分析响应"""
    failed_drug_name: str
    failed_indication_id: str
    impact_severity: str
    total_affected_drugs: int
    total_affected_trials: int
    total_affected_companies: int
    affected_combinations: list[dict[str, Any]]
    recommendations: list[str]
    analysis: str = ""


class OpportunityRequest(BaseModel):
    """空白点挖掘请求"""
    min_prevalence: int = 10000
    max_soc_score: float = 6.0
    min_unmet_need: float = 7.0
    include_llm_analysis: bool = True


class OpportunityResponse(BaseModel):
    """空白点挖掘响应"""
    total_opportunities: int
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int
    high_priority: list[dict[str, Any]]
    recommendations: list[str]
    analysis_summary: str = ""


class IntegrityCheckRequest(BaseModel):
    """数据诚信检查请求"""
    p_value_threshold: float = 0.05
    censoring_threshold: float = 0.5
    include_llm_analysis: bool = True


class IntegrityCheckResponse(BaseModel):
    """数据诚信检查响应"""
    total_checked: int
    suspicious_count: int
    critical_count: int
    high_risk_count: int
    medium_risk_count: int
    suspicious_data: list[dict[str, Any]]
    recommendations: list[str]
    summary: str = ""


# ==================== 竞争分析 API ====================

@router.post("/competition", response_model=CompetitionAnalysisResponse)
async def analyze_competition(request: CompetitionAnalysisRequest):
    """竞争坍缩模拟
    
    分析药物失败对联合用药方案和管线生态的影响。
    
    当某药物在特定适应症实验失败时，系统会:
    1. 找出所有依赖该药物的联合用药方案
    2. 评估受影响的公司和管线
    3. 计算调整后的成功率预期
    4. 给出投资建议
    """
    analyzer = CompetitionAnalyzer()
    
    try:
        result = await analyzer.analyze_collapse(
            failed_drug_id=request.failed_drug_id,
            failed_indication_id=request.failed_indication_id,
            include_llm_analysis=request.include_llm_analysis,
        )
        
        return CompetitionAnalysisResponse(
            failed_drug_name=result.failed_drug_name,
            failed_indication_id=result.failed_indication_id,
            impact_severity=result.impact_severity,
            total_affected_drugs=result.total_affected_drugs,
            total_affected_trials=result.total_affected_trials,
            total_affected_companies=result.total_affected_companies,
            affected_combinations=[c.model_dump() for c in result.affected_combinations],
            recommendations=result.recommendations,
            analysis=result.raw_analysis,
        )
    except Exception as e:
        logger.error(f"Competition analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/competition/vulnerable/{drug_id}")
async def find_vulnerable_combinations(drug_id: str):
    """查找依赖特定药物的联合用药方案
    
    用于评估单个药物失败可能产生的连锁影响。
    """
    analyzer = CompetitionAnalyzer()
    
    try:
        results = await analyzer.find_vulnerable_combos(drug_id)
        return {
            "drug_id": drug_id,
            "vulnerable_combos": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"Find vulnerable combos failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 空白点挖掘 API ====================

@router.post("/opportunity", response_model=OpportunityResponse)
async def discover_opportunities(request: OpportunityRequest):
    """空白点挖掘
    
    发现高价值投资机会，搜索:
    - 高患病人数
    - 低现有疗法疗效
    - 无在研 Phase III 管线
    
    的适应症，这些通常是极具投资价值的"处女地"。
    """
    analyzer = OpportunityAnalyzer()
    
    try:
        result = await analyzer.discover_opportunities(
            min_prevalence=request.min_prevalence,
            max_soc_score=request.max_soc_score,
            min_unmet_need=request.min_unmet_need,
            include_llm_analysis=request.include_llm_analysis,
        )
        
        return OpportunityResponse(
            total_opportunities=result.total_opportunities,
            high_priority_count=len(result.high_priority),
            medium_priority_count=len(result.medium_priority),
            low_priority_count=len(result.low_priority),
            high_priority=[o.model_dump() for o in result.high_priority[:10]],
            recommendations=result.recommendations,
            analysis_summary=result.analysis_summary,
        )
    except Exception as e:
        logger.error(f"Opportunity discovery failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/opportunity/unmet-need")
async def find_high_unmet_need(min_score: float = 8.0):
    """查找高未满足需求的适应症"""
    analyzer = OpportunityAnalyzer()
    
    try:
        results = await analyzer.find_high_unmet_need(min_score)
        return {
            "min_unmet_need_score": min_score,
            "indications": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"Find high unmet need failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/opportunity/landscape/{indication_id}")
async def get_indication_landscape(indication_id: str):
    """获取适应症竞争格局"""
    analyzer = OpportunityAnalyzer()
    
    try:
        result = await analyzer.analyze_indication_landscape(indication_id)
        return result
    except Exception as e:
        logger.error(f"Get indication landscape failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 数据诚信检查 API ====================

@router.post("/integrity", response_model=IntegrityCheckResponse)
async def check_data_integrity(request: IntegrityCheckRequest):
    """数据诚信预警
    
    识别可疑的临床数据:
    - p值极显著但HR接近1
    - 高删失点密度
    - 统计学结果与临床意义不匹配
    
    当发现问题时，系统会自动触发"数据可靠性存疑"标签。
    """
    checker = DataIntegrityChecker()
    
    try:
        result = await checker.check_integrity(
            p_value_threshold=request.p_value_threshold,
            censoring_threshold=request.censoring_threshold,
            include_llm_analysis=request.include_llm_analysis,
        )
        
        return IntegrityCheckResponse(
            total_checked=result.total_checked,
            suspicious_count=result.suspicious_count,
            critical_count=result.critical_count,
            high_risk_count=result.high_risk_count,
            medium_risk_count=result.medium_risk_count,
            suspicious_data=[d.model_dump() for d in result.suspicious_data[:20]],
            recommendations=result.recommendations,
            summary=result.summary,
        )
    except Exception as e:
        logger.error(f"Integrity check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/integrity/suspicious")
async def find_suspicious_patterns():
    """查找可疑数据模式"""
    checker = DataIntegrityChecker()
    
    try:
        results = await checker.find_suspicious_patterns()
        return {
            "suspicious_patterns": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"Find suspicious patterns failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

