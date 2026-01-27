// Activity 实现
// 封装所有 Agent 的具体业务逻辑
package activity

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/biovalue-ai/biovalue/pkg/cache"
	"github.com/biovalue-ai/biovalue/pkg/config"
	"github.com/biovalue-ai/biovalue/pkg/llm"
	"github.com/biovalue-ai/biovalue/pkg/metrics"
	"go.temporal.io/sdk/activity"
	"go.uber.org/zap"
)

// Activities 包含所有 Activity 的依赖
type Activities struct {
	config    *config.Config
	logger    *zap.Logger
	llmClient *llm.Client
	cache     *cache.RedisCache
}

// NewActivities 创建 Activities 实例
func NewActivities(cfg *config.Config, logger *zap.Logger) (*Activities, error) {
	llmClient, err := llm.NewClient(cfg.LLM)
	if err != nil {
		return nil, fmt.Errorf("failed to create LLM client: %w", err)
	}

	redisCache, err := cache.NewRedisCache(cfg.Storage.Redis)
	if err != nil {
		return nil, fmt.Errorf("failed to create Redis cache: %w", err)
	}

	return &Activities{
		config:    cfg,
		logger:    logger,
		llmClient: llmClient,
		cache:     redisCache,
	}, nil
}

// Close 关闭资源
func (a *Activities) Close() error {
	if a.cache != nil {
		return a.cache.Close()
	}
	return nil
}

// FinancialAuditorActivity 财务审计 Agent
func (a *Activities) FinancialAuditorActivity(ctx context.Context, input FinancialAuditorInput) (*FinancialResult, error) {
	logger := a.logger.With(zap.String("activity", "FinancialAuditor"), zap.String("ticker", input.Ticker))
	info := activity.GetInfo(ctx)
	
	startTime := time.Now()
	defer func() {
		metrics.ActivityDuration.WithLabelValues("FinancialAuditor", "A1", "success").Observe(time.Since(startTime).Seconds())
	}()

	// 1. 检查缓存
	cacheKey := fmt.Sprintf("company:%s:financials", input.Ticker)
	cached, err := a.cache.Get(ctx, cacheKey)
	if err == nil && cached != "" {
		logger.Info("Cache hit for financial data")
		metrics.CacheHitRate.WithLabelValues("get", "hit").Inc()
		
		var result FinancialResult
		if err := json.Unmarshal([]byte(cached), &result); err == nil {
			return &result, nil
		}
	}
	metrics.CacheHitRate.WithLabelValues("get", "miss").Inc()

	// 2. 心跳
	activity.RecordHeartbeat(ctx, "Analyzing financial report...")

	// 3. 调用 LLM 分析财报
	prompt := fmt.Sprintf(`你是一位创新药财务分析专家。请分析以下公司的财务健康状况：
公司代码: %s
财报路径: %s

请提取并计算以下指标：
1. 现金及等价物 (Cash and Cash Equivalents)
2. 年度烧钱速度 (Annual Burn Rate)
3. 现金跑道月数 (Cash Runway = Cash / Monthly Burn Rate)
4. 研发费用 (R&D Expenses)
5. 经营性现金流 (Operating Cash Flow)

请给出财务健康评分 (1-100) 和风险提示。

请以 JSON 格式返回结果。`, input.Ticker, input.ReportPath)

	response, err := a.llmClient.Infer(ctx, &llm.InferRequest{
		TraceID:      info.WorkflowExecution.RunID,
		AgentID:      "A1_FinancialAuditor",
		SystemPrompt: financialAuditorSystemPrompt,
		UserPrompt:   prompt,
		ImagePaths:   []string{input.ReportPath},
	})
	if err != nil {
		logger.Error("LLM inference failed", zap.Error(err))
		return nil, fmt.Errorf("LLM inference failed: %w", err)
	}

	// 4. 解析结果
	var result FinancialResult
	if err := json.Unmarshal([]byte(response.FinalAnswer), &result); err != nil {
		logger.Error("Failed to parse LLM response", zap.Error(err), zap.String("response", response.FinalAnswer))
		return nil, fmt.Errorf("failed to parse LLM response: %w", err)
	}

	result.Ticker = input.Ticker
	result.UpdatedAt = time.Now()

	// 5. 存入缓存
	resultJSON, _ := json.Marshal(result)
	if err := a.cache.Set(ctx, cacheKey, string(resultJSON), 24*time.Hour); err != nil {
		logger.Warn("Failed to cache result", zap.Error(err))
	}

	logger.Info("Financial analysis completed",
		zap.Float64("cash_runway", result.Metrics.CashRunwayMonths),
		zap.Int("health_score", result.HealthScore),
	)

	return &result, nil
}

// PipelineScoutActivity 管线扫描 Agent
func (a *Activities) PipelineScoutActivity(ctx context.Context, input PipelineScoutInput) (*PipelineResult, error) {
	logger := a.logger.With(zap.String("activity", "PipelineScout"), zap.String("ticker", input.Ticker))
	info := activity.GetInfo(ctx)
	
	startTime := time.Now()
	defer func() {
		metrics.ActivityDuration.WithLabelValues("PipelineScout", "A2", "success").Observe(time.Since(startTime).Seconds())
	}()

	// 1. 检查缓存
	cacheKey := fmt.Sprintf("company:%s:pipeline:raw", input.Ticker)
	cached, err := a.cache.Get(ctx, cacheKey)
	if err == nil && cached != "" {
		logger.Info("Cache hit for pipeline data")
		metrics.CacheHitRate.WithLabelValues("get", "hit").Inc()
		
		var result PipelineResult
		if err := json.Unmarshal([]byte(cached), &result); err == nil {
			// 检查数据是否过期 (24小时)
			if time.Since(result.DataAsOf) < 24*time.Hour {
				return &result, nil
			}
		}
	}
	metrics.CacheHitRate.WithLabelValues("get", "miss").Inc()

	activity.RecordHeartbeat(ctx, "Scanning drug pipelines...")

	// 2. 调用 LLM 提取管线信息
	prompt := fmt.Sprintf(`你是一位医药管线研究专家。请搜索并提取以下公司的在研管线信息：
公司代码: %s

请从公司官网、ClinicalTrials.gov、CDE 等数据源获取以下信息：
对于每个药物管线，提取：
1. 药物名称 (Drug Name)
2. 靶点 (Target)
3. 适应症 (Indication)
4. 临床阶段 (Phase: Preclinical/Phase1/Phase1_2/Phase2/Phase2_3/Phase3/Approved)
5. 分子类型 (Modality: 小分子/抗体/ADC/CAR-T/mRNA等)
6. NCT编号 (如有)

请以 JSON 数组格式返回所有管线。`, input.Ticker)

	response, err := a.llmClient.Infer(ctx, &llm.InferRequest{
		TraceID:      info.WorkflowExecution.RunID,
		AgentID:      "A2_PipelineScout",
		SystemPrompt: pipelineScoutSystemPrompt,
		UserPrompt:   prompt,
		EnableTools:  true,
		Tools: []llm.Tool{
			{Name: "web_search", MCPServer: "mcp-web-search"},
		},
	})
	if err != nil {
		return nil, fmt.Errorf("LLM inference failed: %w", err)
	}

	// 3. 解析结果
	var pipelines []DrugPipeline
	if err := json.Unmarshal([]byte(response.FinalAnswer), &pipelines); err != nil {
		return nil, fmt.Errorf("failed to parse pipeline data: %w", err)
	}

	result := &PipelineResult{
		Ticker:    input.Ticker,
		Pipelines: pipelines,
		DataAsOf:  time.Now(),
	}

	// 4. 存入缓存
	resultJSON, _ := json.Marshal(result)
	_ = a.cache.Set(ctx, cacheKey, string(resultJSON), 24*time.Hour)

	logger.Info("Pipeline scan completed", zap.Int("pipeline_count", len(pipelines)))
	return result, nil
}

// ClinicalAssessorActivity 临床评估 Agent - 针对单条管线
// 每条管线启动一个独立的智能体进行竞争力分析
func (a *Activities) ClinicalAssessorActivity(ctx context.Context, input ClinicalAssessorInput) (*ClinicalAssessment, error) {
	logger := a.logger.With(
		zap.String("activity", "ClinicalAssessor"),
		zap.String("ticker", input.Ticker),
		zap.String("drug", input.Pipeline.DrugName),
		zap.String("target", input.Pipeline.Target),
	)
	info := activity.GetInfo(ctx)

	startTime := time.Now()
	defer func() {
		metrics.ActivityDuration.WithLabelValues("ClinicalAssessor", "A3", "success").Observe(time.Since(startTime).Seconds())
	}()

	// 检查缓存 - 针对单条管线
	cacheKey := fmt.Sprintf("company:%s:pipeline:%s:clinical", input.Ticker, input.Pipeline.DrugName)
	cached, err := a.cache.Get(ctx, cacheKey)
	if err == nil && cached != "" {
		var result ClinicalAssessment
		if err := json.Unmarshal([]byte(cached), &result); err == nil {
			logger.Info("Cache hit for clinical assessment")
			metrics.CacheHitRate.WithLabelValues("get", "hit").Inc()
			return &result, nil
		}
	}
	metrics.CacheHitRate.WithLabelValues("get", "miss").Inc()

	activity.RecordHeartbeat(ctx, fmt.Sprintf("Assessing clinical competitiveness for %s...", input.Pipeline.DrugName))

	pipelineJSON, _ := json.Marshal(input.Pipeline)
	prompt := fmt.Sprintf(`你是一位首席医学官(CMO)助手，专注于单一药物管线的临床竞争力分析。

公司代码: %s
待分析管线:
%s

请针对这一条管线进行深入分析：

1. **竞品识别与对比**
   - 列出全球范围内同靶点(%s)的在研和已上市药物
   - 进行 Head-to-Head 数据对比（如有）
   - 分析安全性 (AEs) 与有效性 (ORR, PFS, OS) 差异

2. **Best-in-Class 潜力评估**
   - 该药物相比现有标准疗法有何优势?
   - 是否有差异化的临床数据支撑?

3. **临床成功率 (POS) 估算**
   - 基于当前临床阶段 (%s) 的基础 POS
   - 根据数据表现调整后的 POS

4. **竞争评级**
   - BiC (Best-in-Class): 数据显著优于现有标准
   - FiC (First-in-Class): 全球首创机制
   - MeToo: 同质化竞争
   - BelowAverage: 数据弱于竞品

请以 JSON 格式返回分析结果:
{
  "drug_name": "string",
  "target": "string",
  "indication": "string",
  "phase": "string",
  "pos_score": float (0.0-1.0),
  "competitive_landscape": "string (详细描述竞争格局)",
  "clinical_advantage": "string (临床优势总结)",
  "rating": "BiC|FiC|MeToo|BelowAverage",
  "key_competitors": ["string"],
  "data_sources": ["string"]
}`, input.Ticker, string(pipelineJSON), input.Pipeline.Target, input.Pipeline.Phase)

	response, err := a.llmClient.Infer(ctx, &llm.InferRequest{
		TraceID:      info.WorkflowExecution.RunID,
		AgentID:      fmt.Sprintf("A3_ClinicalAssessor_%s", input.Pipeline.DrugName),
		SystemPrompt: clinicalAssessorSystemPrompt,
		UserPrompt:   prompt,
		EnableTools:  true,
		Tools: []llm.Tool{
			{Name: "web_search", MCPServer: "mcp-web-search"},
		},
	})
	if err != nil {
		return nil, fmt.Errorf("LLM inference failed for %s: %w", input.Pipeline.DrugName, err)
	}

	var result ClinicalAssessment
	if err := json.Unmarshal([]byte(response.FinalAnswer), &result); err != nil {
		return nil, fmt.Errorf("failed to parse clinical assessment for %s: %w", input.Pipeline.DrugName, err)
	}

	// 确保基本信息正确
	result.DrugName = input.Pipeline.DrugName
	result.Target = input.Pipeline.Target
	result.Indication = input.Pipeline.Indication
	result.Phase = input.Pipeline.Phase

	// 存入缓存
	resultJSON, _ := json.Marshal(result)
	_ = a.cache.Set(ctx, cacheKey, string(resultJSON), 12*time.Hour)

	logger.Info("Clinical assessment completed",
		zap.String("drug", result.DrugName),
		zap.Float64("pos", result.POSScore),
		zap.String("rating", result.Rating),
	)

	return &result, nil
}

// MarketStrategistActivity 市场与BD战略分析 Agent - 针对单条管线
// 紧接着临床评估，为每条管线进行市场分析
func (a *Activities) MarketStrategistActivity(ctx context.Context, input MarketStrategistInput) (*MarketAssessment, error) {
	logger := a.logger.With(
		zap.String("activity", "MarketStrategist"),
		zap.String("ticker", input.Ticker),
		zap.String("drug", input.Pipeline.DrugName),
		zap.String("indication", input.Pipeline.Indication),
	)
	info := activity.GetInfo(ctx)

	startTime := time.Now()
	defer func() {
		metrics.ActivityDuration.WithLabelValues("MarketStrategist", "A4_A5", "success").Observe(time.Since(startTime).Seconds())
	}()

	// 检查缓存 - 针对单条管线
	cacheKey := fmt.Sprintf("company:%s:pipeline:%s:market", input.Ticker, input.Pipeline.DrugName)
	cached, err := a.cache.Get(ctx, cacheKey)
	if err == nil && cached != "" {
		var result MarketAssessment
		if err := json.Unmarshal([]byte(cached), &result); err == nil {
			logger.Info("Cache hit for market assessment")
			metrics.CacheHitRate.WithLabelValues("get", "hit").Inc()
			return &result, nil
		}
	}
	metrics.CacheHitRate.WithLabelValues("get", "miss").Inc()

	activity.RecordHeartbeat(ctx, fmt.Sprintf("Analyzing market for %s...", input.Pipeline.DrugName))

	pipelineJSON, _ := json.Marshal(input.Pipeline)
	clinicalJSON, _ := json.Marshal(input.Clinical)

	prompt := fmt.Sprintf(`你是一位医药市场与BD战略分析师，专注于单一药物管线的商业化前景分析。

公司代码: %s
待分析管线:
%s

该管线的临床评估结果:
%s

请针对这一条管线进行深入的市场与BD分析：

1. **国内市场预测**
   - 目标适应症 (%s) 的流行病学数据
   - TAM (总潜在市场) 估算
   - 考虑竞争格局后的市场渗透率预测
   - 峰值销售额预测

2. **BD出海分析**
   - 该靶点 (%s) 的全球热度
   - License-out 潜力评估
   - 基于临床评级 (%s) 估算:
     * 首付款 (Upfront) 潜力
     * 里程碑金额潜力
     * 特许权使用费率
   - 参考近期可比交易

3. **风险调整后收入**
   - 结合 POS (%.2f) 计算风险调整后收入

请以 JSON 格式返回分析结果:
{
  "drug_name": "string",
  "target": "string",
  "indication": "string",
  "domestic": {
    "tam": float,
    "penetration_rate": float (0-1),
    "peak_sales": float,
    "currency": "USD"
  },
  "bd_outlook": {
    "upfront_potential": float,
    "milestone_potential": float,
    "royalty_rate": float (0-1),
    "target_region": "string",
    "comparable_deals": ["string"]
  },
  "risk_adjusted_revenue": float,
  "assumptions": ["string"]
}`, input.Ticker, string(pipelineJSON), string(clinicalJSON),
		input.Pipeline.Indication,
		input.Pipeline.Target,
		input.Clinical.Rating,
		input.Clinical.POSScore)

	response, err := a.llmClient.Infer(ctx, &llm.InferRequest{
		TraceID:      info.WorkflowExecution.RunID,
		AgentID:      fmt.Sprintf("A4_A5_MarketStrategist_%s", input.Pipeline.DrugName),
		SystemPrompt: marketStrategistSystemPrompt,
		UserPrompt:   prompt,
		EnableTools:  true,
		Tools: []llm.Tool{
			{Name: "web_search", MCPServer: "mcp-web-search"},
		},
	})
	if err != nil {
		return nil, fmt.Errorf("LLM inference failed for %s: %w", input.Pipeline.DrugName, err)
	}

	var result MarketAssessment
	if err := json.Unmarshal([]byte(response.FinalAnswer), &result); err != nil {
		return nil, fmt.Errorf("failed to parse market assessment for %s: %w", input.Pipeline.DrugName, err)
	}

	// 确保基本信息正确
	result.DrugName = input.Pipeline.DrugName
	result.Target = input.Pipeline.Target
	result.Indication = input.Pipeline.Indication

	// 存入缓存
	resultJSON, _ := json.Marshal(result)
	_ = a.cache.Set(ctx, cacheKey, string(resultJSON), 6*time.Hour)

	logger.Info("Market assessment completed",
		zap.String("drug", result.DrugName),
		zap.Float64("risk_adjusted_revenue", result.RiskAdjustedRevenue),
	)

	return &result, nil
}

// ValuationActuaryActivity 估值精算 Agent
func (a *Activities) ValuationActuaryActivity(ctx context.Context, input ValuationActuaryInput) (*ValuationResult, error) {
	logger := a.logger.With(zap.String("activity", "ValuationActuary"), zap.String("ticker", input.Ticker))
	info := activity.GetInfo(ctx)

	startTime := time.Now()
	defer func() {
		metrics.ActivityDuration.WithLabelValues("ValuationActuary", "A7", "success").Observe(time.Since(startTime).Seconds())
	}()

	activity.RecordHeartbeat(ctx, "Building valuation models...")

	financialJSON, _ := json.Marshal(input.Financial)
	clinicalJSON, _ := json.Marshal(input.Clinical)
	marketJSON, _ := json.Marshal(input.Market)

	prompt := fmt.Sprintf(`你是一位医药精算师/估值分析师。请使用 rNPV (风险调整净现值) 和 DCF (现金流折现) 模型进行估值。

公司代码: %s
财务数据: %s
临床评估 (所有管线): %s
市场预测 (所有管线): %s

rNPV 公式: rNPV = Σ [CF_t × P(S)] / (1 + WACC)^t
其中 P(S) 为临床成功概率, WACC 通常设定在 10%%-12%%。

请基于每条管线的独立评估结果，综合计算公司整体估值：

1. 汇总所有管线的风险调整后收入
2. 考虑公司财务状况 (现金跑道等)
3. 计算三种场景估值：
   - 乐观 (Bull Case): 高 POS，高渗透率，BD 成功
   - 中性 (Base Case): 行业平均水平，不考虑BD
   - 悲观 (Bear Case): 临床失败，融资受阻

对于每个场景，预测：1Y, 3Y, 5Y, 10Y 的市值

请以 JSON 格式返回估值结果和假设条件。`, input.Ticker, string(financialJSON), string(clinicalJSON), string(marketJSON))

	response, err := a.llmClient.Infer(ctx, &llm.InferRequest{
		TraceID:      info.WorkflowExecution.RunID,
		AgentID:      "A7_ValuationActuary",
		SystemPrompt: valuationActuarySystemPrompt,
		UserPrompt:   prompt,
		EnableTools:  true,
		Tools: []llm.Tool{
			{Name: "code_execute", MCPServer: "sandbox-fusion"},
		},
	})
	if err != nil {
		return nil, fmt.Errorf("LLM inference failed: %w", err)
	}

	var result ValuationResult
	if err := json.Unmarshal([]byte(response.FinalAnswer), &result); err != nil {
		return nil, fmt.Errorf("failed to parse valuation result: %w", err)
	}

	logger.Info("Valuation completed",
		zap.Float64("base_case_1y", result.BaseCase.Value1Y),
		zap.Float64("wacc", result.Assumptions.WACC),
	)
	return &result, nil
}

// ReportGeneratorActivity 报告生成 Agent
func (a *Activities) ReportGeneratorActivity(ctx context.Context, input ReportGeneratorInput) (*ReportResult, error) {
	logger := a.logger.With(zap.String("activity", "ReportGenerator"), zap.String("ticker", input.Ticker))
	info := activity.GetInfo(ctx)

	startTime := time.Now()
	defer func() {
		metrics.ActivityDuration.WithLabelValues("ReportGenerator", "A6", "success").Observe(time.Since(startTime).Seconds())
	}()

	activity.RecordHeartbeat(ctx, "Generating investment report...")

	allDataJSON, _ := json.Marshal(input)

	prompt := fmt.Sprintf(`你是一位资深医药投资研究员。请根据以下数据生成一份完整的投研报告。

数据汇总:
%s

报告要求：
1. 使用 Markdown 格式
2. 包含以下章节：
   - 公司概览
   - 财务健康度分析
   - 管线竞争力评估 (逐一分析每条管线)
   - 市场机会与BD前景 (逐一分析每条管线)
   - 估值分析与投资建议
   - 关键风险提示

3. 对于每条管线，需要展示：
   - 临床竞争力评级和 POS
   - 市场规模和BD潜力
   - 风险调整后收入贡献

4. 所有数值必须标注来源
5. 给出明确的投资建议（买入/持有/卖出）

请直接输出 Markdown 格式的报告内容。`, string(allDataJSON))

	response, err := a.llmClient.Infer(ctx, &llm.InferRequest{
		TraceID:      info.WorkflowExecution.RunID,
		AgentID:      "A6_ReportGenerator",
		SystemPrompt: reportGeneratorSystemPrompt,
		UserPrompt:   prompt,
	})
	if err != nil {
		return nil, fmt.Errorf("LLM inference failed: %w", err)
	}

	result := &ReportResult{
		Ticker:          input.Ticker,
		MarkdownContent: response.FinalAnswer,
		KeyRisks:        extractKeyRisks(response.FinalAnswer),
		Recommendation:  extractRecommendation(response.FinalAnswer),
		GeneratedAt:     time.Now(),
	}

	// 存入缓存
	cacheKey := fmt.Sprintf("company:%s:report:final", input.Ticker)
	resultJSON, _ := json.Marshal(result)
	_ = a.cache.Set(ctx, cacheKey, string(resultJSON), 7*24*time.Hour)

	logger.Info("Report generated", zap.String("recommendation", result.Recommendation))
	return result, nil
}

// NotifyCompensationFailure 通知补偿失败
func (a *Activities) NotifyCompensationFailure(ctx context.Context, stepName string, errorMsg string) error {
	a.logger.Error("Compensation failed, manual intervention required",
		zap.String("step", stepName),
		zap.String("error", errorMsg),
	)
	// TODO: 发送告警通知
	return nil
}

// 辅助函数
func extractKeyRisks(content string) []string {
	// 简单实现，实际应使用更复杂的解析逻辑
	return []string{"临床试验失败风险", "市场竞争风险", "融资风险", "监管审批风险"}
}

func extractRecommendation(content string) string {
	// 简单实现
	return "持有"
}

// System Prompts
const (
	financialAuditorSystemPrompt = `你是一位创新药财务分析专家。你的核心职责是评估生物医药公司的财务安全性。
由于创新药公司通常处于亏损状态，你需要重点计算"现金跑道"(Cash Runway)。
所有数值必须来源于官方财报，不得捏造数据。`

	pipelineScoutSystemPrompt = `你是一位医药管线研究专家。你的职责是全面扫描并结构化整理公司的在研药物管线。
数据来源必须是可靠的：公司官网、ClinicalTrials.gov、CDE等官方数据库。
确保提取的信息准确、完整。`

	clinicalAssessorSystemPrompt = `你是一位首席医学官(CMO)助手，专注于单一药物管线的临床数据分析和竞争力评估。
你需要针对每条管线独立进行深入调研，客观评估药物的临床优势，基于公开的临床数据进行竞品对比。
评估必须有数据支撑，不得主观臆断。每次只分析一条管线，确保分析的深度和准确性。`

	marketStrategistSystemPrompt = `你是一位医药市场与BD战略分析师，专注于单一药物管线的商业化前景分析。
你需要针对每条管线独立进行市场调研，基于流行病学数据、市场调研报告进行TAM估算和市场预测。
BD分析需要参考近期的交易案例和行业趋势。每次只分析一条管线，确保分析的深度和准确性。`

	valuationActuarySystemPrompt = `你是一位医药精算师/估值分析师，精通 rNPV 和 DCF 估值模型。
你需要综合所有管线的独立评估结果，计算公司整体估值。
估值必须基于合理的假设，假设条件必须明确列出。
三种场景（Bull/Base/Bear）的差异化必须有合理依据。`

	reportGeneratorSystemPrompt = `你是一位资深医药投资研究员，擅长撰写专业的投研报告。
报告需要逐一展示每条管线的分析结果，包括临床评估和市场预测。
报告必须逻辑清晰、数据详实、结论明确。
风险提示必须全面，投资建议必须谨慎。`
)
