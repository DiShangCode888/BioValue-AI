// Activity 类型定义
package activity

import "time"

// ============== Financial Auditor ==============

// FinancialAuditorInput 财务审计输入
type FinancialAuditorInput struct {
	Ticker     string `json:"ticker"`
	ReportPath string `json:"report_path"`
}

// FinancialResult 财务分析结果
type FinancialResult struct {
	Ticker      string           `json:"ticker"`
	Metrics     FinancialMetrics `json:"metrics"`
	HealthScore int              `json:"health_score"`
	RiskWarning string           `json:"risk_warning"`
	SourceURL   string           `json:"source_url"`
	UpdatedAt   time.Time        `json:"updated_at"`
}

// FinancialMetrics 财务指标
type FinancialMetrics struct {
	CashOnHand        float64 `json:"cash_on_hand"`
	AnnualBurnRate    float64 `json:"annual_burn_rate"`
	CashRunwayMonths  float64 `json:"cash_runway_months"`
	RAndDExpenses     float64 `json:"r_and_d_expenses"`
	OperatingCashFlow float64 `json:"operating_cash_flow"`
}

// ============== Pipeline Scout ==============

// PipelineScoutInput 管线扫描输入
type PipelineScoutInput struct {
	Ticker     string `json:"ticker"`
	CompanyURL string `json:"company_url,omitempty"`
}

// PipelineResult 管线扫描结果
type PipelineResult struct {
	Ticker    string         `json:"ticker"`
	Pipelines []DrugPipeline `json:"pipelines"`
	DataAsOf  time.Time      `json:"data_as_of"`
}

// DrugPipeline 药物管线
type DrugPipeline struct {
	DrugName   string `json:"drug_name"`
	Target     string `json:"target"`
	Indication string `json:"indication"`
	Phase      string `json:"phase"`
	Modality   string `json:"modality"`
	NCTID      string `json:"nct_id,omitempty"`
}

// ============== Clinical Assessor (单管线) ==============

// ClinicalAssessorInput 临床评估输入 - 针对单条管线
type ClinicalAssessorInput struct {
	Ticker   string       `json:"ticker"`
	Pipeline DrugPipeline `json:"pipeline"` // 单条管线
}

// ClinicalAssessment 单条管线的临床评估结果
type ClinicalAssessment struct {
	DrugName             string   `json:"drug_name"`
	Target               string   `json:"target"`
	Indication           string   `json:"indication"`
	Phase                string   `json:"phase"`
	POSScore             float64  `json:"pos_score"`
	CompetitiveLandscape string   `json:"competitive_landscape"`
	ClinicalAdvantage    string   `json:"clinical_advantage"`
	Rating               string   `json:"rating"` // BiC, FiC, MeToo, BelowAverage
	KeyCompetitors       []string `json:"key_competitors"`
	DataSources          []string `json:"data_sources"`
}

// ClinicalResult 临床评估聚合结果 (所有管线)
type ClinicalResult struct {
	Ticker      string               `json:"ticker"`
	Assessments []ClinicalAssessment `json:"assessments"`
	UpdatedAt   time.Time            `json:"updated_at"`
}

// CoreAsset 核心资产评估 (保留兼容性)
type CoreAsset struct {
	DrugName             string  `json:"drug_name"`
	POSScore             float64 `json:"pos_score"`
	CompetitiveLandscape string  `json:"competitive_landscape"`
	ClinicalAdvantage    string  `json:"clinical_advantage"`
	Rating               string  `json:"rating"`
}

// ============== Market Strategist (单管线) ==============

// MarketStrategistInput 市场策略输入 - 针对单条管线
type MarketStrategistInput struct {
	Ticker     string              `json:"ticker"`
	Pipeline   DrugPipeline        `json:"pipeline"`   // 单条管线
	Clinical   *ClinicalAssessment `json:"clinical"`   // 该管线的临床评估结果
}

// MarketAssessment 单条管线的市场分析结果
type MarketAssessment struct {
	DrugName            string         `json:"drug_name"`
	Target              string         `json:"target"`
	Indication          string         `json:"indication"`
	Domestic            MarketForecast `json:"domestic"`
	BDOutlook           BDForecast     `json:"bd_outlook"`
	RiskAdjustedRevenue float64        `json:"risk_adjusted_revenue"`
	Assumptions         []string       `json:"assumptions"`
}

// MarketResult 市场分析聚合结果 (所有管线)
type MarketResult struct {
	Ticker                   string             `json:"ticker"`
	Assessments              []MarketAssessment `json:"assessments"`
	TotalRiskAdjustedRevenue float64            `json:"total_risk_adjusted_revenue"`
	UpdatedAt                time.Time          `json:"updated_at"`
}

// MarketForecast 市场预测
type MarketForecast struct {
	TAM             float64 `json:"tam"`
	PenetrationRate float64 `json:"penetration_rate"`
	PeakSales       float64 `json:"peak_sales"`
	Currency        string  `json:"currency"`
}

// BDForecast BD 预测
type BDForecast struct {
	UpfrontPotential   float64  `json:"upfront_potential"`
	MilestonePotential float64  `json:"milestone_potential"`
	RoyaltyRate        float64  `json:"royalty_rate"`
	TargetRegion       string   `json:"target_region"`
	ComparableDeals    []string `json:"comparable_deals,omitempty"`
}

// ============== Pipeline Analysis Result (单管线完整分析) ==============

// PipelineAnalysisInput 单管线分析输入
type PipelineAnalysisInput struct {
	Ticker   string       `json:"ticker"`
	Pipeline DrugPipeline `json:"pipeline"`
}

// PipelineAnalysisResult 单管线完整分析结果 (临床 + 市场)
type PipelineAnalysisResult struct {
	Pipeline DrugPipeline       `json:"pipeline"`
	Clinical ClinicalAssessment `json:"clinical"`
	Market   MarketAssessment   `json:"market"`
}

// ============== Valuation Actuary ==============

// ValuationActuaryInput 估值输入
type ValuationActuaryInput struct {
	Ticker    string           `json:"ticker"`
	Financial *FinancialResult `json:"financial"`
	Clinical  *ClinicalResult  `json:"clinical"`
	Market    *MarketResult    `json:"market"`
}

// ValuationResult 估值结果
type ValuationResult struct {
	BullCase    ValuationScenario    `json:"bull_case"`
	BaseCase    ValuationScenario    `json:"base_case"`
	BearCase    ValuationScenario    `json:"bear_case"`
	Assumptions ValuationAssumptions `json:"assumptions"`
}

// ValuationScenario 估值场景
type ValuationScenario struct {
	Value1Y   float64 `json:"value_1y"`
	Value3Y   float64 `json:"value_3y"`
	Value5Y   float64 `json:"value_5y"`
	Value10Y  float64 `json:"value_10y"`
	Rationale string  `json:"rationale"`
}

// ValuationAssumptions 估值假设
type ValuationAssumptions struct {
	WACC           float64 `json:"wacc"`
	TerminalGrowth float64 `json:"terminal_growth"`
	AvgPOS         float64 `json:"avg_pos"`
	Methodology    string  `json:"methodology"`
}

// ============== Report Generator ==============

// ReportGeneratorInput 报告生成输入
type ReportGeneratorInput struct {
	Ticker            string                   `json:"ticker"`
	Financial         *FinancialResult         `json:"financial"`
	Pipeline          *PipelineResult          `json:"pipeline"`
	PipelineAnalyses  []PipelineAnalysisResult `json:"pipeline_analyses"` // 每条管线的详细分析
	Clinical          *ClinicalResult          `json:"clinical"`
	Market            *MarketResult            `json:"market"`
	Valuation         *ValuationResult         `json:"valuation"`
}

// ReportResult 报告结果
type ReportResult struct {
	Ticker          string    `json:"ticker"`
	MarkdownContent string    `json:"markdown_content"`
	KeyRisks        []string  `json:"key_risks"`
	Recommendation  string    `json:"recommendation"`
	GeneratedAt     time.Time `json:"generated_at"`
}
