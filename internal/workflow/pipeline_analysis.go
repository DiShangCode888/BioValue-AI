// 单管线分析子工作流
// 对每条管线独立执行临床评估和市场分析
package workflow

import (
	"time"

	"github.com/biovalue-ai/biovalue/internal/activity"
	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

// PipelineAnalysisInput 单管线分析输入
type PipelineAnalysisInput struct {
	Ticker   string                `json:"ticker"`
	Pipeline activity.DrugPipeline `json:"pipeline"`
}

// PipelineAnalysisWorkflow 单管线分析子工作流
// 每条管线启动一个独立的智能体进行临床评估，完成后紧接着启动市场分析
func PipelineAnalysisWorkflow(ctx workflow.Context, input PipelineAnalysisInput) (*activity.PipelineAnalysisResult, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting Pipeline Analysis Workflow",
		"ticker", input.Ticker,
		"drug", input.Pipeline.DrugName,
		"target", input.Pipeline.Target,
		"phase", input.Pipeline.Phase,
	)

	// 配置 Activity 选项
	activityOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 8 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:        5 * time.Second,
			BackoffCoefficient:     2.0,
			MaximumInterval:        1 * time.Minute,
			MaximumAttempts:        3,
			NonRetryableErrorTypes: []string{"FatalError", "ValidationError"},
		},
	}
	ctx = workflow.WithActivityOptions(ctx, activityOpts)

	result := &activity.PipelineAnalysisResult{
		Pipeline: input.Pipeline,
	}

	// ============== Step 1: 临床评估 (CMO 助手) ==============
	logger.Info("Starting Clinical Assessment",
		"drug", input.Pipeline.DrugName,
	)

	var clinicalResult activity.ClinicalAssessment
	err := workflow.ExecuteActivity(ctx, "ClinicalAssessorActivity",
		activity.ClinicalAssessorInput{
			Ticker:   input.Ticker,
			Pipeline: input.Pipeline,
		}).Get(ctx, &clinicalResult)

	if err != nil {
		logger.Error("Clinical Assessment failed",
			"drug", input.Pipeline.DrugName,
			"error", err,
		)
		// 使用默认值继续
		clinicalResult = activity.ClinicalAssessment{
			DrugName:             input.Pipeline.DrugName,
			Target:               input.Pipeline.Target,
			Indication:           input.Pipeline.Indication,
			Phase:                input.Pipeline.Phase,
			POSScore:             getDefaultPOS(input.Pipeline.Phase),
			CompetitiveLandscape: "Unable to assess",
			ClinicalAdvantage:    "Unable to assess",
			Rating:               "Unknown",
		}
	}

	result.Clinical = clinicalResult

	logger.Info("Clinical Assessment completed",
		"drug", input.Pipeline.DrugName,
		"pos", clinicalResult.POSScore,
		"rating", clinicalResult.Rating,
	)

	// ============== Step 2: 市场与BD分析 (紧接着临床评估) ==============
	logger.Info("Starting Market Analysis",
		"drug", input.Pipeline.DrugName,
	)

	var marketResult activity.MarketAssessment
	err = workflow.ExecuteActivity(ctx, "MarketStrategistActivity",
		activity.MarketStrategistInput{
			Ticker:   input.Ticker,
			Pipeline: input.Pipeline,
			Clinical: &clinicalResult, // 传入临床评估结果
		}).Get(ctx, &marketResult)

	if err != nil {
		logger.Error("Market Analysis failed",
			"drug", input.Pipeline.DrugName,
			"error", err,
		)
		// 使用默认值
		marketResult = activity.MarketAssessment{
			DrugName:   input.Pipeline.DrugName,
			Target:     input.Pipeline.Target,
			Indication: input.Pipeline.Indication,
			Domestic: activity.MarketForecast{
				TAM:      0,
				Currency: "USD",
			},
			BDOutlook: activity.BDForecast{
				TargetRegion: "Unknown",
			},
			RiskAdjustedRevenue: 0,
		}
	}

	result.Market = marketResult

	logger.Info("Market Analysis completed",
		"drug", input.Pipeline.DrugName,
		"risk_adjusted_revenue", marketResult.RiskAdjustedRevenue,
	)

	logger.Info("Pipeline Analysis Workflow completed",
		"ticker", input.Ticker,
		"drug", input.Pipeline.DrugName,
		"clinical_rating", clinicalResult.Rating,
		"pos", clinicalResult.POSScore,
		"revenue", marketResult.RiskAdjustedRevenue,
	)

	return result, nil
}

// getDefaultPOS 根据临床阶段返回默认 POS
func getDefaultPOS(phase string) float64 {
	switch phase {
	case "Preclinical":
		return 0.05
	case "Phase1":
		return 0.10
	case "Phase1_2":
		return 0.15
	case "Phase2":
		return 0.30
	case "Phase2_3":
		return 0.50
	case "Phase3":
		return 0.60
	case "Approved":
		return 1.0
	default:
		return 0.20
	}
}

