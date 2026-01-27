// Prometheus 指标定义
package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	// WorkflowDuration 工作流执行时长
	WorkflowDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "biovalue_workflow_duration_seconds",
			Help:    "Workflow execution duration",
			Buckets: []float64{1, 5, 10, 30, 60, 120, 300, 600},
		},
		[]string{"workflow_type", "status"},
	)

	// ActivityDuration 活动执行时长
	ActivityDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "biovalue_activity_duration_seconds",
			Help:    "Activity execution duration",
			Buckets: []float64{0.1, 0.5, 1, 5, 10, 30, 60},
		},
		[]string{"activity_name", "agent_id", "status"},
	)

	// LLMTokenUsage Token 使用量
	LLMTokenUsage = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "biovalue_llm_token_usage_total",
			Help: "Total LLM tokens consumed",
		},
		[]string{"model", "type"}, // type: prompt/completion
	)

	// LLMLatency LLM 调用延迟
	LLMLatency = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "biovalue_llm_latency_seconds",
			Help:    "LLM inference latency",
			Buckets: []float64{0.5, 1, 2, 5, 10, 30, 60, 120},
		},
		[]string{"model", "agent_id"},
	)

	// CacheHitRate 缓存命中率
	CacheHitRate = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "biovalue_cache_operations_total",
			Help: "Cache operations count",
		},
		[]string{"operation", "result"}, // result: hit/miss
	)

	// MCPToolCalls MCP 工具调用
	MCPToolCalls = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "biovalue_mcp_tool_calls_total",
			Help: "MCP tool invocations",
		},
		[]string{"server", "tool", "status"},
	)

	// MCPToolLatency MCP 工具延迟
	MCPToolLatency = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "biovalue_mcp_tool_latency_seconds",
			Help:    "MCP tool execution latency",
			Buckets: []float64{0.1, 0.5, 1, 5, 10, 30, 60},
		},
		[]string{"server", "tool"},
	)

	// CircuitBreakerState 熔断器状态
	CircuitBreakerState = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "biovalue_circuit_breaker_state",
			Help: "Circuit breaker state (0=closed, 1=open, 2=half_open)",
		},
		[]string{"service"},
	)

	// ErrorsTotal 错误计数
	ErrorsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "biovalue_errors_total",
			Help: "Total errors by level and code",
		},
		[]string{"level", "code"},
	)

	// DLQMessages DLQ 消息数
	DLQMessages = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "biovalue_dlq_messages",
			Help: "Number of messages in Dead Letter Queue",
		},
	)

	// ActiveWorkflows 活跃工作流数
	ActiveWorkflows = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "biovalue_active_workflows",
			Help: "Number of currently active workflows",
		},
	)

	// LLMCost LLM 成本
	LLMCost = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "biovalue_llm_cost_usd",
			Help: "Total LLM cost in USD",
		},
		[]string{"model"},
	)
)

