// Saga 补偿模式实现
// 用于工作流失败时的事务回滚
package workflow

import (
	"go.temporal.io/sdk/workflow"
)

// CompensationStep 补偿步骤
type CompensationStep struct {
	Name string
	Fn   func(ctx workflow.Context) error
}

// SagaCompensation Saga 补偿管理器
type SagaCompensation struct {
	steps []CompensationStep
}

// NewSagaCompensation 创建新的 Saga 补偿管理器
func NewSagaCompensation() *SagaCompensation {
	return &SagaCompensation{
		steps: make([]CompensationStep, 0),
	}
}

// AddCompensation 添加补偿步骤 (LIFO 顺序)
func (s *SagaCompensation) AddCompensation(name string, fn func(ctx workflow.Context) error) {
	// 在头部插入，确保 LIFO 顺序执行
	s.steps = append([]CompensationStep{{Name: name, Fn: fn}}, s.steps...)
}

// Execute 执行所有补偿操作
func (s *SagaCompensation) Execute(ctx workflow.Context) error {
	logger := workflow.GetLogger(ctx)
	
	for _, step := range s.steps {
		logger.Info("Executing compensation", "step", step.Name)
		
		if err := step.Fn(ctx); err != nil {
			logger.Error("Compensation failed",
				"step", step.Name,
				"error", err,
			)
			// 记录补偿失败，通知人工介入
			_ = workflow.ExecuteActivity(ctx, "NotifyCompensationFailure", step.Name, err.Error()).Get(ctx, nil)
			// 继续执行其他补偿步骤
		} else {
			logger.Info("Compensation completed", "step", step.Name)
		}
	}
	
	return nil
}

// Clear 清空补偿步骤
func (s *SagaCompensation) Clear() {
	s.steps = make([]CompensationStep, 0)
}

// Len 返回补偿步骤数量
func (s *SagaCompensation) Len() int {
	return len(s.steps)
}

