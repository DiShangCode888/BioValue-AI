# 竞争坍缩分析
"""
竞争坍缩模拟:
如果药物X在适应症A的一线治疗实验中失败，
图谱会自动沿路径找到所有以药物X作为底层逻辑的联用方案，
并调低它们的成功率期望。
"""

from pydantic import BaseModel, Field
from typing import Any

from src.knowledge import get_neo4j_client
from src.knowledge.queries import COMPETITION_COLLAPSE_QUERY, FIND_AFFECTED_COMBOS_QUERY
from src.llms import get_llm
from src.utils import get_logger

logger = get_logger(__name__)


class AffectedCombo(BaseModel):
    """受影响的联合用药方案"""
    partner_drug_id: str
    partner_drug_name: str
    synergy_score: float | None = None
    combo_node_name: str | None = None
    company: str | None = None
    treatment_line: str | None = None
    trial_nct: str | None = None
    trial_phase: str | None = None
    trial_status: str | None = None
    adjusted_success_rate: float | None = None


class CollapseAnalysisResult(BaseModel):
    """竞争坍缩分析结果"""
    failed_drug_id: str
    failed_drug_name: str
    failed_indication_id: str
    affected_combinations: list[AffectedCombo] = Field(default_factory=list)
    total_affected_drugs: int = 0
    total_affected_trials: int = 0
    total_affected_companies: int = 0
    impact_severity: str = "low"  # low, medium, high, critical
    recommendations: list[str] = Field(default_factory=list)
    raw_analysis: str = ""


class CompetitionAnalyzer:
    """竞争分析器
    
    执行竞争坍缩模拟，分析药物失败对整个管线生态的影响。
    """
    
    def __init__(self):
        self._client = get_neo4j_client()
    
    async def analyze_collapse(
        self,
        failed_drug_id: str,
        failed_indication_id: str,
        include_llm_analysis: bool = True,
    ) -> CollapseAnalysisResult:
        """分析药物失败的连锁影响
        
        Args:
            failed_drug_id: 失败药物ID
            failed_indication_id: 失败的适应症ID
            include_llm_analysis: 是否包含 LLM 分析
            
        Returns:
            CollapseAnalysisResult: 分析结果
        """
        logger.info(f"Analyzing collapse for drug {failed_drug_id} in indication {failed_indication_id}")
        
        await self._client.connect()
        
        # 执行图谱查询
        query_results = await self._client.execute_query(
            COMPETITION_COLLAPSE_QUERY,
            {
                "failed_drug_id": failed_drug_id,
                "failed_indication_id": failed_indication_id,
            }
        )
        
        if not query_results:
            return CollapseAnalysisResult(
                failed_drug_id=failed_drug_id,
                failed_drug_name="Unknown",
                failed_indication_id=failed_indication_id,
            )
        
        collapse_data = query_results[0].get("collapse_analysis", {})
        
        # 解析受影响的联合用药
        affected_combos = []
        for combo in collapse_data.get("affected_combinations", []):
            if combo.get("partner_drug_id"):
                affected_combos.append(AffectedCombo(
                    partner_drug_id=combo.get("partner_drug_id", ""),
                    partner_drug_name=combo.get("partner_drug", ""),
                    synergy_score=combo.get("synergy_score"),
                    combo_node_name=combo.get("combo_node"),
                    company=combo.get("company"),
                    treatment_line=combo.get("treatment_line"),
                    trial_nct=combo.get("trial_nct"),
                    trial_phase=combo.get("trial_phase"),
                    trial_status=combo.get("trial_status"),
                    # 根据协同效应评分调整预期成功率
                    adjusted_success_rate=self._calculate_adjusted_rate(
                        combo.get("synergy_score"),
                        combo.get("trial_phase")
                    ),
                ))
        
        impact_summary = collapse_data.get("impact_summary", {})
        
        # 评估影响严重程度
        severity = self._assess_severity(
            total_drugs=impact_summary.get("total_affected_drugs", 0),
            total_trials=impact_summary.get("total_affected_trials", 0),
            total_companies=impact_summary.get("total_affected_companies", 0),
        )
        
        result = CollapseAnalysisResult(
            failed_drug_id=failed_drug_id,
            failed_drug_name=collapse_data.get("failed_drug", "Unknown"),
            failed_indication_id=failed_indication_id,
            affected_combinations=affected_combos,
            total_affected_drugs=impact_summary.get("total_affected_drugs", 0),
            total_affected_trials=impact_summary.get("total_affected_trials", 0),
            total_affected_companies=impact_summary.get("total_affected_companies", 0),
            impact_severity=severity,
        )
        
        # LLM 深度分析
        if include_llm_analysis and affected_combos:
            analysis, recommendations = await self._llm_analyze(result)
            result.raw_analysis = analysis
            result.recommendations = recommendations
        
        return result
    
    def _calculate_adjusted_rate(
        self,
        synergy_score: float | None,
        trial_phase: str | None
    ) -> float | None:
        """计算调整后的成功率"""
        if synergy_score is None:
            return None
        
        # 基础成功率（按阶段）
        base_rates = {
            "Phase I": 0.10,
            "Phase II": 0.20,
            "Phase III": 0.50,
            "已获批": 0.90,
        }
        base_rate = base_rates.get(trial_phase, 0.15)
        
        # 如果底层药物失败，调低成功率
        # 协同效应越强，影响越大
        synergy_factor = synergy_score / 10 if synergy_score else 0.5
        adjustment_factor = 0.3 + (0.4 * (1 - synergy_factor))  # 30%-70% 降幅
        
        return round(base_rate * adjustment_factor, 3)
    
    def _assess_severity(
        self,
        total_drugs: int,
        total_trials: int,
        total_companies: int
    ) -> str:
        """评估影响严重程度"""
        score = total_drugs * 3 + total_trials * 2 + total_companies * 1
        
        if score >= 20:
            return "critical"
        elif score >= 10:
            return "high"
        elif score >= 5:
            return "medium"
        else:
            return "low"
    
    async def _llm_analyze(
        self,
        result: CollapseAnalysisResult
    ) -> tuple[str, list[str]]:
        """使用 LLM 进行深度分析"""
        llm = get_llm("reasoning")
        
        prompt = f"""请分析以下竞争坍缩模拟结果，并给出投资建议:

失败药物: {result.failed_drug_name}
适应症ID: {result.failed_indication_id}
影响严重程度: {result.impact_severity}

受影响的联合用药方案:
"""
        for combo in result.affected_combinations[:10]:  # 最多分析10个
            prompt += f"""
- 合作药物: {combo.partner_drug_name}
  - 公司: {combo.company or 'N/A'}
  - 协同效应评分: {combo.synergy_score or 'N/A'}
  - 临床阶段: {combo.trial_phase or 'N/A'}
  - 调整后成功率: {combo.adjusted_success_rate or 'N/A'}
"""
        
        prompt += """
请从以下角度分析:
1. 对各联合用药方案的具体影响
2. 最需要重新评估的管线
3. 投资组合调整建议
4. 潜在的替代机会
"""
        
        response = await llm.generate(
            prompt=prompt,
            system_prompt="你是一位资深的创新药投资分析师，专注于竞争格局分析和风险评估。",
        )
        
        # 提取建议
        recommendations = []
        lines = response.content.split("\n")
        in_recommendations = False
        
        for line in lines:
            if "建议" in line.lower():
                in_recommendations = True
                continue
            if in_recommendations and line.strip().startswith(("-", "•", "*", "1", "2", "3")):
                rec = line.strip().lstrip("-•*0123456789. ")
                if rec:
                    recommendations.append(rec)
        
        return response.content, recommendations[:5]
    
    async def find_vulnerable_combos(
        self,
        drug_id: str
    ) -> list[dict[str, Any]]:
        """查找所有依赖特定药物的联合用药方案
        
        用于风险评估，识别潜在脆弱的管线。
        """
        await self._client.connect()
        
        results = await self._client.execute_query(
            FIND_AFFECTED_COMBOS_QUERY,
            {"drug_id": drug_id}
        )
        
        return results

