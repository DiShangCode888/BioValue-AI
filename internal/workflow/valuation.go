// 估值子工作流
// 使用 rNPV 和 DCF 模型进行动态市值建模
package workflow

import (
	"time"

	"github.com/biovalue-ai/biovalue/internal/activity"
	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

// ValuationInput 估值工作流输入
type ValuationInput struct {
	Ticker    string                    `json:"ticker"`
	Financial *activity.FinancialResult `json:"financial"`
	Clinical  *activity.ClinicalResult  `json:"clinical"`
	Market    *activity.MarketResult    `json:"market"`
}

// ValuationWorkflow 估值子工作流
func ValuationWorkflow(ctx workflow.Context, input ValuationInput) (*activity.ValuationResult, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting Valuation Workflow", "ticker", input.Ticker)

	activityOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 5 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:    5 * time.Second,
			BackoffCoefficient: 2.0,
			MaximumInterval:    30 * time.Second,
			MaximumAttempts:    3,
		},
	}
	ctx = workflow.WithActivityOptions(ctx, activityOpts)

	var result activity.ValuationResult
	err := workflow.ExecuteActivity(ctx, "ValuationActuaryActivity",
		activity.ValuationActuaryInput{
			Ticker:    input.Ticker,
			Financial: input.Financial,
			Clinical:  input.Clinical,
			Market:    input.Market,
		}).Get(ctx, &result)

	if err != nil {
		logger.Error("ValuationActuaryActivity failed", "error", err)
		return nil, err
	}

	logger.Info("Valuation Workflow completed",
		"ticker", input.Ticker,
		"base_case_1y", result.BaseCase.Value1Y,
	)

	return &result, nil
}

