// 结构化日志
package logging

import (
	"os"

	"github.com/biovalue-ai/biovalue/pkg/config"
	"go.temporal.io/sdk/log"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

// NewLogger 创建日志记录器
func NewLogger(cfg config.LoggingConfig) (*zap.Logger, error) {
	// 解析日志级别
	var level zapcore.Level
	switch cfg.Level {
	case "debug":
		level = zapcore.DebugLevel
	case "info":
		level = zapcore.InfoLevel
	case "warn":
		level = zapcore.WarnLevel
	case "error":
		level = zapcore.ErrorLevel
	default:
		level = zapcore.InfoLevel
	}

	// 配置编码器
	var encoderConfig zapcore.EncoderConfig
	if cfg.Format == "json" {
		encoderConfig = zap.NewProductionEncoderConfig()
	} else {
		encoderConfig = zap.NewDevelopmentEncoderConfig()
	}
	encoderConfig.TimeKey = "timestamp"
	encoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder

	// 创建编码器
	var encoder zapcore.Encoder
	if cfg.Format == "json" {
		encoder = zapcore.NewJSONEncoder(encoderConfig)
	} else {
		encoder = zapcore.NewConsoleEncoder(encoderConfig)
	}

	// 配置输出
	var output zapcore.WriteSyncer
	switch cfg.Output {
	case "stdout":
		output = zapcore.AddSync(os.Stdout)
	case "stderr":
		output = zapcore.AddSync(os.Stderr)
	default:
		output = zapcore.AddSync(os.Stdout)
	}

	core := zapcore.NewCore(encoder, output, level)
	logger := zap.New(core, zap.AddCaller(), zap.AddStacktrace(zapcore.ErrorLevel))

	return logger, nil
}

// TemporalLogger 适配 Temporal SDK 的日志接口
type TemporalLogger struct {
	logger *zap.Logger
}

// NewTemporalLogger 创建 Temporal 日志适配器
func NewTemporalLogger(logger *zap.Logger) log.Logger {
	return &TemporalLogger{logger: logger.With(zap.String("component", "temporal"))}
}

func (l *TemporalLogger) Debug(msg string, keyvals ...interface{}) {
	l.logger.Debug(msg, toZapFields(keyvals)...)
}

func (l *TemporalLogger) Info(msg string, keyvals ...interface{}) {
	l.logger.Info(msg, toZapFields(keyvals)...)
}

func (l *TemporalLogger) Warn(msg string, keyvals ...interface{}) {
	l.logger.Warn(msg, toZapFields(keyvals)...)
}

func (l *TemporalLogger) Error(msg string, keyvals ...interface{}) {
	l.logger.Error(msg, toZapFields(keyvals)...)
}

func toZapFields(keyvals []interface{}) []zap.Field {
	if len(keyvals)%2 != 0 {
		return nil
	}

	fields := make([]zap.Field, 0, len(keyvals)/2)
	for i := 0; i < len(keyvals); i += 2 {
		key, ok := keyvals[i].(string)
		if !ok {
			continue
		}
		fields = append(fields, zap.Any(key, keyvals[i+1]))
	}
	return fields
}

// LogEntry 结构化日志条目
type LogEntry struct {
	Timestamp string                 `json:"timestamp"`
	Level     string                 `json:"level"`
	TraceID   string                 `json:"trace_id"`
	SpanID    string                 `json:"span_id"`
	Service   string                 `json:"service"`
	Component string                 `json:"component"`
	Message   string                 `json:"message"`
	Error     *ErrorInfo             `json:"error,omitempty"`
	Context   map[string]interface{} `json:"context,omitempty"`
	Duration  *float64               `json:"duration_ms,omitempty"`
}

// ErrorInfo 错误信息
type ErrorInfo struct {
	Type    string `json:"type"`
	Message string `json:"message"`
	Stack   string `json:"stack,omitempty"`
}

// SanitizeForLog 敏感数据脱敏
func SanitizeForLog(data map[string]interface{}) map[string]interface{} {
	sensitiveFields := map[string]bool{
		"api_key":  true,
		"password": true,
		"token":    true,
		"secret":   true,
		"key":      true,
	}

	result := make(map[string]interface{})
	for k, v := range data {
		if sensitiveFields[k] {
			result[k] = "***REDACTED***"
		} else {
			result[k] = v
		}
	}
	return result
}

