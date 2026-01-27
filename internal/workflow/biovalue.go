// BioValue 主工作流
// 协调多个 Agent 完成创新药市值评估
package workflow

import (
	"fmt"
	"time"

	"github.com/biovalue-ai/biovalue/internal/activity"
	"github.com/biovalue-ai/biovalue/pkg/errors"
	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

// WorkflowInput 工作流输入
type WorkflowInput struct {
	Ticker     string            `json:"ticker"`      // 股票代码
	ReportPath string            `json:"report_path"` // 财报路径
	Options    map[string]string `json:"options"`     // 额外选项
}

// WorkflowOutput 工作流输出
type WorkflowOutput struct {
	Ticker            string                          `json:"ticker"`
	Financial         *activity.FinancialResult       `json:"financial"`
	Pipeline          *activity.PipelineResult        `json:"pipeline"`
	PipelineAnalyses  []activity.PipelineAnalysisResult `json:"pipeline_analyses"` // 每条管线的详细分析
	Clinical          *activity.ClinicalResult        `json:"clinical"`
	Market            *activity.MarketResult          `json:"market"`
	Valuation         *activity.ValuationResult       `json:"valuation"`
	Report            *activity.ReportResult          `json:"report"`
	TraceID           string                          `json:"trace_id"`
	CompletedAt       time.Time                       `json:"completed_at"`
}

// ProgressInfo 进度信息 (用于 Query)
type ProgressInfo struct {
	CurrentAgent       string   `json:"current_agent"`
	CompletedSteps     []string `json:"completed_steps"`
	TotalSteps         int      `json:"total_steps"`
	Progress           float64  `json:"progress"`
	PipelineProgress   map[string]string `json:"pipeline_progress"` // 每条管线的进度
}

// InterventionSignal 人工干预信号
type InterventionSignal struct {
	Type    string                 `json:"type"`    // pause, resume, cancel, modify
	AgentID string                 `json:"agent_id"`
	Data    map[string]interface{} `json:"data"`
}

// BioValueWorkflow 创新药市值评估主工作流
func BioValueWorkflow(ctx workflow.Context, input WorkflowInput) (*WorkflowOutput, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting BioValue Workflow", "ticker", input.Ticker)

	// 初始化 Saga 补偿
	saga := NewSagaCompensation()

	// 进度跟踪
	var currentAgent string
	completedSteps := make([]string, 0)
	pipelineProgress := make(map[string]string) // 每条管线的进度

	// 注册 Query Handler
	err := workflow.SetQueryHandler(ctx, "progress", func() (ProgressInfo, error) {
		totalSteps := 4 + len(pipelineProgress)*2 // 基础步骤 + 每条管线的临床+市场
		return ProgressInfo{
			CurrentAgent:     currentAgent,
			CompletedSteps:   completedSteps,
			TotalSteps:       totalSteps,
			Progress:         float64(len(completedSteps)) / float64(totalSteps) * 100,
			PipelineProgress: pipelineProgress,
		}, nil
	})
	if err != nil {
		return nil, fmt.Errorf("failed to set query handler: %w", err)
	}

	// 配置 Activity 选项
	activityOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:        5 * time.Second,
			BackoffCoefficient:     2.0,
			MaximumInterval:        1 * time.Minute,
			MaximumAttempts:        5,
			NonRetryableErrorTypes: []string{"FatalError", "ValidationError"},
		},
	}
	ctx = workflow.WithActivityOptions(ctx, activityOpts)

	// 信号通道 - 人工干预
	isPaused := false
	signalChan := workflow.GetSignalChannel(ctx, "human-intervention")

	// 启动信号监听 goroutine
	workflow.Go(ctx, func(gCtx workflow.Context) {
		for {
			var signal InterventionSignal
			signalChan.Receive(gCtx, &signal)
			
			switch signal.Type {
			case "pause":
				isPaused = true
				logger.Info("Workflow paused by signal")
			case "resume":
				isPaused = false
				logger.Info("Workflow resumed by signal")
			case "cancel":
				logger.Info("Workflow cancelled by signal")
				return
			}
		}
	})

	// 等待恢复的辅助函数
	waitForResume := func() {
		_ = workflow.Await(ctx, func() bool { return !isPaused })
	}

	output := &WorkflowOutput{
		Ticker:  input.Ticker,
		TraceID: workflow.GetInfo(ctx).WorkflowExecution.RunID,
	}

	// ============== Step 1 & 2: 并行执行财务审计和管线扫描 ==============
	currentAgent = "FinancialAuditor,PipelineScout"
	
	var financialResult activity.FinancialResult
	var pipelineResult activity.PipelineResult

	financialFuture := workflow.ExecuteActivity(ctx, "FinancialAuditorActivity",
		activity.FinancialAuditorInput{
			Ticker:     input.Ticker,
			ReportPath: input.ReportPath,
		})
	
	pipelineFuture := workflow.ExecuteActivity(ctx, "PipelineScoutActivity",
		activity.PipelineScoutInput{
			Ticker: input.Ticker,
		})

	// 等待并行任务完成
	selector := workflow.NewSelector(ctx)
	
	selector.AddFuture(financialFuture, func(f workflow.Future) {
		if err := f.Get(ctx, &financialResult); err != nil {
			logger.Error("FinancialAuditor failed", "error", err)
		} else {
			completedSteps = append(completedSteps, "FinancialAuditor")
			output.Financial = &financialResult
			saga.AddCompensation("financial", func(ctx workflow.Context) error {
				return cleanupFinancialData(ctx, input.Ticker)
			})
		}
	})

	selector.AddFuture(pipelineFuture, func(f workflow.Future) {
		if err := f.Get(ctx, &pipelineResult); err != nil {
			logger.Error("PipelineScout failed", "error", err)
		} else {
			completedSteps = append(completedSteps, "PipelineScout")
			output.Pipeline = &pipelineResult
			saga.AddCompensation("pipeline", func(ctx workflow.Context) error {
				return cleanupPipelineData(ctx, input.Ticker)
			})
		}
	})

	for i := 0; i < 2; i++ {
		selector.Select(ctx)
	}

	// 检查暂停
	if isPaused {
		waitForResume()
	}

	// ============== Step 3: 对每条管线并行执行临床评估 + 市场分析 ==============
	// 每条管线启动一个独立的智能体进行临床评估，完成后紧接着启动市场分析
	currentAgent = "PipelineAnalysis"
	
	// 初始化管线进度
	for _, p := range pipelineResult.Pipelines {
		pipelineProgress[p.DrugName] = "pending"
	}

	// 使用 Child Workflow 处理每条管线的完整分析
	pipelineAnalyses := make([]activity.PipelineAnalysisResult, 0, len(pipelineResult.Pipelines))
	pipelineFutures := make([]workflow.ChildWorkflowFuture, 0, len(pipelineResult.Pipelines))

	// 并行启动每条管线的分析 Child Workflow
	for i, pipeline := range pipelineResult.Pipelines {
		childOpts := workflow.ChildWorkflowOptions{
			WorkflowID: fmt.Sprintf("pipeline-analysis-%s-%s-%d",
				input.Ticker, workflow.GetInfo(ctx).WorkflowExecution.RunID, i),
		}
		childCtx := workflow.WithChildOptions(ctx, childOpts)

		future := workflow.ExecuteChildWorkflow(childCtx, PipelineAnalysisWorkflow,
			PipelineAnalysisInput{
				Ticker:   input.Ticker,
				Pipeline: pipeline,
			})
		pipelineFutures = append(pipelineFutures, future)
		pipelineProgress[pipeline.DrugName] = "in_progress"
	}

	// 使用 Selector 收集所有管线分析结果
	pipelineSelector := workflow.NewSelector(ctx)
	for i, future := range pipelineFutures {
		idx := i
		drugName := pipelineResult.Pipelines[idx].DrugName
		pipelineSelector.AddFuture(future, func(f workflow.Future) {
			var result activity.PipelineAnalysisResult
			if err := f.Get(ctx, &result); err != nil {
				logger.Error("Pipeline analysis failed", "drug", drugName, "error", err)
				pipelineProgress[drugName] = "failed"
			} else {
				pipelineAnalyses = append(pipelineAnalyses, result)
				pipelineProgress[drugName] = "completed"
				completedSteps = append(completedSteps, fmt.Sprintf("PipelineAnalysis:%s", drugName))
			}
		})
	}

	// 等待所有管线分析完成
	for range pipelineFutures {
		pipelineSelector.Select(ctx)
	}

	output.PipelineAnalyses = pipelineAnalyses

	// 聚合临床评估结果
	clinicalResult := aggregateClinicalResults(input.Ticker, pipelineAnalyses)
	output.Clinical = &clinicalResult
	completedSteps = append(completedSteps, "ClinicalAggregation")

	// 聚合市场分析结果
	marketResult := aggregateMarketResults(input.Ticker, pipelineAnalyses)
	output.Market = &marketResult
	completedSteps = append(completedSteps, "MarketAggregation")

	if isPaused {
		waitForResume()
	}

	// ============== Step 4: 估值计算 (Child Workflow) ==============
	currentAgent = "ValuationActuary"
	
	childOpts := workflow.ChildWorkflowOptions{
		WorkflowID: fmt.Sprintf("valuation-%s-%s", input.Ticker, workflow.GetInfo(ctx).WorkflowExecution.RunID),
	}
	childCtx := workflow.WithChildOptions(ctx, childOpts)

	var valuationResult activity.ValuationResult
	if err := workflow.ExecuteChildWorkflow(childCtx, ValuationWorkflow,
		ValuationInput{
			Ticker:    input.Ticker,
			Financial: &financialResult,
			Clinical:  &clinicalResult,
			Market:    &marketResult,
		}).Get(ctx, &valuationResult); err != nil {
		classifiedErr := errors.ClassifyError(err)
		if classifiedErr.Level >= errors.L2Intervention {
			_ = saga.Execute(ctx)
			return nil, fmt.Errorf("valuation workflow failed: %w", err)
		}
	} else {
		completedSteps = append(completedSteps, "ValuationActuary")
		output.Valuation = &valuationResult
	}

	if isPaused {
		waitForResume()
	}

	// ============== Step 5: 研报生成 ==============
	currentAgent = "ReportGenerator"
	
	var reportResult activity.ReportResult
	if err := workflow.ExecuteActivity(ctx, "ReportGeneratorActivity",
		activity.ReportGeneratorInput{
			Ticker:           input.Ticker,
			Financial:        &financialResult,
			Pipeline:         &pipelineResult,
			PipelineAnalyses: pipelineAnalyses,
			Clinical:         &clinicalResult,
			Market:           &marketResult,
			Valuation:        &valuationResult,
		}).Get(ctx, &reportResult); err != nil {
		logger.Warn("ReportGenerator failed", "error", err)
	} else {
		completedSteps = append(completedSteps, "ReportGenerator")
		output.Report = &reportResult
	}

	output.CompletedAt = workflow.Now(ctx)
	
	logger.Info("BioValue Workflow completed",
		"ticker", input.Ticker,
		"completed_steps", completedSteps,
		"pipeline_count", len(pipelineAnalyses),
	)

	return output, nil
}

// aggregateClinicalResults 聚合所有管线的临床评估结果
func aggregateClinicalResults(ticker string, analyses []activity.PipelineAnalysisResult) activity.ClinicalResult {
	assessments := make([]activity.ClinicalAssessment, 0, len(analyses))
	for _, a := range analyses {
		assessments = append(assessments, a.Clinical)
	}
	return activity.ClinicalResult{
		Ticker:      ticker,
		Assessments: assessments,
	}
}

// aggregateMarketResults 聚合所有管线的市场分析结果
func aggregateMarketResults(ticker string, analyses []activity.PipelineAnalysisResult) activity.MarketResult {
	assessments := make([]activity.MarketAssessment, 0, len(analyses))
	totalRevenue := 0.0
	for _, a := range analyses {
		assessments = append(assessments, a.Market)
		totalRevenue += a.Market.RiskAdjustedRevenue
	}
	return activity.MarketResult{
		Ticker:                   ticker,
		Assessments:              assessments,
		TotalRiskAdjustedRevenue: totalRevenue,
	}
}

// 补偿函数
func cleanupFinancialData(ctx workflow.Context, ticker string) error {
	return workflow.ExecuteActivity(ctx, "CleanupCacheActivity", ticker, "financials").Get(ctx, nil)
}

func cleanupPipelineData(ctx workflow.Context, ticker string) error {
	return workflow.ExecuteActivity(ctx, "CleanupCacheActivity", ticker, "pipeline").Get(ctx, nil)
}
