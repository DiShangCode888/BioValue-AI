// BioValue-AI Worker 入口
// 启动 Temporal Worker 处理工作流和活动
package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/biovalue-ai/biovalue/internal/activity"
	"github.com/biovalue-ai/biovalue/internal/workflow"
	"github.com/biovalue-ai/biovalue/pkg/config"
	"github.com/biovalue-ai/biovalue/pkg/logging"
	"github.com/biovalue-ai/biovalue/pkg/tracing"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
	"go.uber.org/zap"
)

func main() {
	// 加载配置
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	// 初始化日志
	logger, err := logging.NewLogger(cfg.Observability.Logging)
	if err != nil {
		log.Fatalf("Failed to initialize logger: %v", err)
	}
	defer logger.Sync()

	// 初始化 Tracing
	tp, err := tracing.InitTracer(cfg.System.ServiceName)
	if err != nil {
		logger.Fatal("Failed to initialize tracer", zap.Error(err))
	}
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		tp.Shutdown(ctx)
	}()

	// 启动 Metrics 服务器
	go startMetricsServer(cfg.Observability.Metrics.Port, logger)

	// 创建 Temporal 客户端
	c, err := client.Dial(client.Options{
		HostPort:  cfg.Temporal.Address,
		Namespace: cfg.Temporal.Namespace,
		Logger:    logging.NewTemporalLogger(logger),
	})
	if err != nil {
		logger.Fatal("Failed to create Temporal client", zap.Error(err))
	}
	defer c.Close()

	// 创建 Activity 依赖
	activities, err := activity.NewActivities(cfg, logger)
	if err != nil {
		logger.Fatal("Failed to create activities", zap.Error(err))
	}
	defer activities.Close()

	// 创建 Worker
	w := worker.New(c, cfg.Temporal.TaskQueue, worker.Options{
		MaxConcurrentActivityExecutionSize:     cfg.Temporal.Worker.MaxConcurrentActivities,
		MaxConcurrentWorkflowTaskExecutionSize: cfg.Temporal.Worker.MaxConcurrentWorkflows,
	})

	// 注册工作流
	w.RegisterWorkflow(workflow.BioValueWorkflow)
	w.RegisterWorkflow(workflow.ValuationWorkflow)
	w.RegisterWorkflow(workflow.PipelineAnalysisWorkflow) // 单管线分析子工作流

	// 注册活动
	w.RegisterActivity(activities.FinancialAuditorActivity)
	w.RegisterActivity(activities.PipelineScoutActivity)
	w.RegisterActivity(activities.ClinicalAssessorActivity)
	w.RegisterActivity(activities.MarketStrategistActivity)
	w.RegisterActivity(activities.ValuationActuaryActivity)
	w.RegisterActivity(activities.ReportGeneratorActivity)
	w.RegisterActivity(activities.NotifyCompensationFailure)

	// 启动 Worker
	logger.Info("Starting BioValue Worker",
		zap.String("task_queue", cfg.Temporal.TaskQueue),
		zap.String("namespace", cfg.Temporal.Namespace),
	)

	// 优雅关闭
	_ , cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-sigChan
		logger.Info("Received shutdown signal, gracefully stopping...")
		cancel()
	}()

	err = w.Run(worker.InterruptCh())
	if err != nil {
		logger.Fatal("Worker failed", zap.Error(err))
	}

	logger.Info("Worker stopped")
}

func startMetricsServer(port int, logger *zap.Logger) {
	mux := http.NewServeMux()
	mux.Handle("/metrics", promhttp.Handler())
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("ok"))
	})
	mux.HandleFunc("/readyz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("ready"))
	})

	addr := fmt.Sprintf(":%d", port)
	logger.Info("Starting metrics server", zap.String("addr", addr))

	if err := http.ListenAndServe(addr, mux); err != nil {
		logger.Error("Metrics server failed", zap.Error(err))
	}
}

