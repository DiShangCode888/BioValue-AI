# 空白点挖掘
"""
空白点挖掘:
搜索"高流行病学数据 + 低SoC疗效 + 无在研Phase III管线"的适应症节点，
这通常是极具投资价值的"处女地"。
"""

from pydantic import BaseModel, Field
from typing import Any

from src.knowledge import get_neo4j_client
from src.knowledge.queries import OPPORTUNITY_DISCOVERY_QUERY, HIGH_UNMET_NEED_QUERY
from src.llms import get_llm
from src.utils import get_logger

logger = get_logger(__name__)


class OpportunityIndication(BaseModel):
    """投资机会适应症"""
    indication_id: str
    indication_name: str
    prevalence: int | None = None
    incidence_annual: int | None = None
    unmet_need_score: float | None = None
    soc_efficacy_score: float | None = None
    current_soc: str | None = None
    soc_years: int | None = None
    market_size: float | None = None
    therapeutic_area: str | None = None
    competing_drugs_count: int = 0
    investment_score: float = 0
    opportunity_level: str = "LOW_OPPORTUNITY"


class OpportunityAnalysisResult(BaseModel):
    """空白点挖掘结果"""
    total_opportunities: int = 0
    high_priority: list[OpportunityIndication] = Field(default_factory=list)
    medium_priority: list[OpportunityIndication] = Field(default_factory=list)
    low_priority: list[OpportunityIndication] = Field(default_factory=list)
    analysis_summary: str = ""
    recommendations: list[str] = Field(default_factory=list)


class OpportunityAnalyzer:
    """机会挖掘分析器
    
    识别高价值投资机会:
    1. 高患病人数
    2. 低现有疗法疗效
    3. 无在研 Phase III 管线
    """
    
    def __init__(self):
        self._client = get_neo4j_client()
    
    async def discover_opportunities(
        self,
        min_prevalence: int = 10000,
        max_soc_score: float = 6.0,
        min_unmet_need: float = 7.0,
        include_llm_analysis: bool = True,
    ) -> OpportunityAnalysisResult:
        """发现投资机会
        
        Args:
            min_prevalence: 最小患病人数
            max_soc_score: 最大SoC疗效评分
            min_unmet_need: 最小未满足需求分数
            include_llm_analysis: 是否包含 LLM 分析
            
        Returns:
            OpportunityAnalysisResult: 分析结果
        """
        logger.info(f"Discovering opportunities with criteria: prevalence>={min_prevalence}, "
                   f"soc<={max_soc_score}, unmet_need>={min_unmet_need}")
        
        await self._client.connect()
        
        # 执行图谱查询
        query_results = await self._client.execute_query(
            OPPORTUNITY_DISCOVERY_QUERY,
            {
                "min_prevalence": min_prevalence,
                "max_soc_score": max_soc_score,
                "min_unmet_need": min_unmet_need,
            }
        )
        
        # 解析结果
        opportunities = []
        for result in query_results:
            opp_data = result.get("opportunity", {})
            indication_data = opp_data.get("indication", {})
            
            opportunities.append(OpportunityIndication(
                indication_id=indication_data.get("id", ""),
                indication_name=indication_data.get("name", ""),
                prevalence=indication_data.get("prevalence"),
                incidence_annual=indication_data.get("incidence_annual"),
                unmet_need_score=indication_data.get("unmet_need_score"),
                soc_efficacy_score=indication_data.get("soc_efficacy_score"),
                current_soc=opp_data.get("current_soc"),
                soc_years=opp_data.get("soc_years"),
                market_size=indication_data.get("market_size"),
                therapeutic_area=indication_data.get("therapeutic_area"),
                competing_drugs_count=opp_data.get("competing_drugs_count", 0),
                investment_score=opp_data.get("investment_score", 0),
            ))
        
        # 按优先级分类
        high_priority = [o for o in opportunities if o.investment_score >= 50]
        medium_priority = [o for o in opportunities if 20 <= o.investment_score < 50]
        low_priority = [o for o in opportunities if o.investment_score < 20]
        
        result = OpportunityAnalysisResult(
            total_opportunities=len(opportunities),
            high_priority=sorted(high_priority, key=lambda x: x.investment_score, reverse=True),
            medium_priority=sorted(medium_priority, key=lambda x: x.investment_score, reverse=True),
            low_priority=sorted(low_priority, key=lambda x: x.investment_score, reverse=True),
        )
        
        # LLM 分析
        if include_llm_analysis and opportunities:
            summary, recommendations = await self._llm_analyze(result)
            result.analysis_summary = summary
            result.recommendations = recommendations
        
        return result
    
    async def find_high_unmet_need(
        self,
        min_unmet_need_score: float = 8.0
    ) -> list[dict[str, Any]]:
        """查找高未满足需求的适应症
        
        Args:
            min_unmet_need_score: 最小未满足需求分数
            
        Returns:
            list[dict]: 适应症列表及管线信息
        """
        await self._client.connect()
        
        results = await self._client.execute_query(
            HIGH_UNMET_NEED_QUERY,
            {"min_unmet_need_score": min_unmet_need_score}
        )
        
        return results
    
    async def analyze_indication_landscape(
        self,
        indication_id: str
    ) -> dict[str, Any]:
        """分析特定适应症的竞争格局
        
        Args:
            indication_id: 适应症ID
            
        Returns:
            dict: 竞争格局分析
        """
        await self._client.connect()
        
        # 获取适应症详情
        indication = await self._client.get_node(indication_id)
        if not indication:
            return {"error": f"Indication {indication_id} not found"}
        
        # 获取所有治疗该适应症的药物
        drugs = await self._client.get_drug_by_indication(indication_id)
        
        # 获取标准疗法
        soc = await self._client.get_indication_soc(indication_id)
        
        return {
            "indication": indication,
            "current_soc": soc,
            "competing_drugs": drugs,
            "total_drugs": len(drugs),
            "phase_distribution": self._calculate_phase_distribution(drugs),
        }
    
    def _calculate_phase_distribution(
        self,
        drugs: list[dict]
    ) -> dict[str, int]:
        """计算管线阶段分布"""
        distribution = {
            "preclinical": 0,
            "phase1": 0,
            "phase2": 0,
            "phase3": 0,
            "approved": 0,
        }
        
        # 这里需要根据实际数据结构调整
        # 简化实现
        return distribution
    
    async def _llm_analyze(
        self,
        result: OpportunityAnalysisResult
    ) -> tuple[str, list[str]]:
        """使用 LLM 进行深度分析"""
        llm = get_llm("reasoning")
        
        prompt = f"""请分析以下空白点挖掘结果，并给出投资建议:

发现的投资机会总数: {result.total_opportunities}

高优先级机会 ({len(result.high_priority)} 个):
"""
        for opp in result.high_priority[:5]:
            prompt += f"""
- {opp.indication_name}
  - 患病人数: {opp.prevalence or 'N/A'}
  - 未满足需求评分: {opp.unmet_need_score or 'N/A'}
  - 当前SoC: {opp.current_soc or 'N/A'}
  - 投资评分: {opp.investment_score:.2f}
"""
        
        prompt += f"""
中优先级机会 ({len(result.medium_priority)} 个)
低优先级机会 ({len(result.low_priority)} 个)

请从以下角度分析:
1. 最具投资价值的适应症及其原因
2. 进入壁垒分析
3. 推荐的投资策略
4. 风险提示
"""
        
        response = await llm.generate(
            prompt=prompt,
            system_prompt="你是一位资深的创新药投资分析师，专注于发现未被满足的医疗需求和投资机会。",
        )
        
        # 提取建议
        recommendations = []
        lines = response.content.split("\n")
        
        for line in lines:
            if line.strip().startswith(("-", "•", "*")) and "建议" not in line:
                rec = line.strip().lstrip("-•*0123456789. ")
                if rec and len(rec) > 10:
                    recommendations.append(rec)
        
        return response.content, recommendations[:5]

