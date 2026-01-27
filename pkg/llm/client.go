// LLM 客户端
package llm

import (
	"context"
	"fmt"
	"time"

	"github.com/biovalue-ai/biovalue/pkg/config"
	"github.com/biovalue-ai/biovalue/pkg/metrics"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// Client LLM 客户端
type Client struct {
	config     config.LLMConfig
	conn       *grpc.ClientConn
	bridgeAddr string
}

// InferRequest 推理请求
type InferRequest struct {
	TraceID      string
	AgentID      string
	SystemPrompt string
	UserPrompt   string
	ImagePaths   []string
	Context      []ContextChunk
	Temperature  float32
	MaxTokens    int32
	EnableTools  bool
	Tools        []Tool
}

// ContextChunk 上下文块
type ContextChunk struct {
	Content        string
	Source         string
	RelevanceScore float32
}

// Tool 工具定义
type Tool struct {
	Name        string
	Description string
	InputSchema string
	MCPServer   string
}

// InferResponse 推理响应
type InferResponse struct {
	TraceID     string
	Status      ResponseStatus
	Thought     *ThoughtChain
	ToolCall    *ToolCall
	FinalAnswer string
	Usage       *UsageMetrics
}

// ResponseStatus 响应状态
type ResponseStatus int

const (
	StatusSuccess ResponseStatus = iota
	StatusToolRequired
	StatusValidationFailed
	StatusRateLimited
	StatusError
)

// ThoughtChain 思维链
type ThoughtChain struct {
	Reasoning  string
	Plan       string
	Confidence float32
}

// ToolCall 工具调用
type ToolCall struct {
	ToolName  string
	ToolInput string
	MCPServer string
}

// UsageMetrics 使用指标
type UsageMetrics struct {
	PromptTokens     int32
	CompletionTokens int32
	TotalTokens      int32
	CostUSD          float64
	Model            string
	LatencyMs        int64
}

// NewClient 创建 LLM 客户端
func NewClient(cfg config.LLMConfig) (*Client, error) {
	// 获取 LLM Bridge 地址
	bridgeAddr := "localhost:50051" // 默认地址

	return &Client{
		config:     cfg,
		bridgeAddr: bridgeAddr,
	}, nil
}

// Connect 连接到 LLM Bridge
func (c *Client) Connect(ctx context.Context) error {
	conn, err := grpc.DialContext(ctx, c.bridgeAddr,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithBlock(),
	)
	if err != nil {
		return fmt.Errorf("failed to connect to LLM Bridge: %w", err)
	}
	c.conn = conn
	return nil
}

// Close 关闭连接
func (c *Client) Close() error {
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

// Infer 执行推理
func (c *Client) Infer(ctx context.Context, req *InferRequest) (*InferResponse, error) {
	startTime := time.Now()

	// 设置默认值
	if req.Temperature == 0 {
		req.Temperature = 0.7
	}
	if req.MaxTokens == 0 {
		req.MaxTokens = 4096
	}

	// TODO: 实际调用 gRPC 服务
	// 这里是模拟实现，实际应通过 gRPC 调用 Python LLM Bridge

	// 模拟响应
	response := &InferResponse{
		TraceID: req.TraceID,
		Status:  StatusSuccess,
		Thought: &ThoughtChain{
			Reasoning:  "分析中...",
			Plan:       "执行计划",
			Confidence: 0.85,
		},
		FinalAnswer: `{"status": "success", "message": "This is a placeholder response"}`,
		Usage: &UsageMetrics{
			PromptTokens:     100,
			CompletionTokens: 200,
			TotalTokens:      300,
			CostUSD:          0.01,
			Model:            c.config.Model,
			LatencyMs:        time.Since(startTime).Milliseconds(),
		},
	}

	// 记录指标
	metrics.LLMTokenUsage.WithLabelValues(c.config.Model, "prompt").Add(float64(response.Usage.PromptTokens))
	metrics.LLMTokenUsage.WithLabelValues(c.config.Model, "completion").Add(float64(response.Usage.CompletionTokens))
	metrics.LLMLatency.WithLabelValues(c.config.Model, req.AgentID).Observe(time.Since(startTime).Seconds())
	metrics.LLMCost.WithLabelValues(c.config.Model).Add(response.Usage.CostUSD)

	return response, nil
}

// InferWithRetry 带重试的推理
func (c *Client) InferWithRetry(ctx context.Context, req *InferRequest, maxRetries int) (*InferResponse, error) {
	var lastErr error
	for i := 0; i < maxRetries; i++ {
		resp, err := c.Infer(ctx, req)
		if err == nil {
			return resp, nil
		}
		lastErr = err
		// 指数退避
		time.Sleep(time.Duration(1<<i) * time.Second)
	}
	return nil, fmt.Errorf("failed after %d retries: %w", maxRetries, lastErr)
}

