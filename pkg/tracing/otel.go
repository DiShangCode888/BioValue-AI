// OpenTelemetry 追踪
package tracing

import (
	"context"
	"os"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"go.opentelemetry.io/otel/trace"
)

var (
	// Version 服务版本
	Version = "1.0.0"
)

// InitTracer 初始化追踪器
func InitTracer(serviceName string) (*sdktrace.TracerProvider, error) {
	endpoint := os.Getenv("OTEL_EXPORTER_ENDPOINT")
	if endpoint == "" {
		endpoint = "localhost:4318"
	}

	exporter, err := otlptracehttp.New(context.Background(),
		otlptracehttp.WithEndpoint(endpoint),
		otlptracehttp.WithInsecure(),
	)
	if err != nil {
		return nil, err
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(resource.NewWithAttributes(
			semconv.SchemaURL,
			semconv.ServiceName(serviceName),
			semconv.ServiceVersion(Version),
			attribute.String("environment", os.Getenv("ENV")),
		)),
		sdktrace.WithSampler(sdktrace.TraceIDRatioBased(0.1)), // 10% 采样
	)

	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	return tp, nil
}

// Tracer 获取追踪器
func Tracer(name string) trace.Tracer {
	return otel.Tracer(name)
}

// SpanFromContext 从上下文获取 Span
func SpanFromContext(ctx context.Context) trace.Span {
	return trace.SpanFromContext(ctx)
}

// StartSpan 开始新的 Span
func StartSpan(ctx context.Context, name string, opts ...trace.SpanStartOption) (context.Context, trace.Span) {
	return otel.Tracer("biovalue").Start(ctx, name, opts...)
}

// AddEvent 添加事件到当前 Span
func AddEvent(ctx context.Context, name string, attrs ...attribute.KeyValue) {
	span := trace.SpanFromContext(ctx)
	span.AddEvent(name, trace.WithAttributes(attrs...))
}

// SetAttributes 设置 Span 属性
func SetAttributes(ctx context.Context, attrs ...attribute.KeyValue) {
	span := trace.SpanFromContext(ctx)
	span.SetAttributes(attrs...)
}

// RecordError 记录错误
func RecordError(ctx context.Context, err error) {
	span := trace.SpanFromContext(ctx)
	span.RecordError(err)
}

// Span 命名规范
// 格式: {component}.{operation}
// 示例:
//   - workflow.BioValueWorkflow
//   - activity.FinancialAuditor
//   - llm.infer
//   - mcp.call.web_search
//   - redis.get
//   - vectordb.search

