// 错误分类与处理
package errors

import (
	"context"
	"errors"
)

// ErrorLevel 错误级别
type ErrorLevel int

const (
	// L1Recoverable 可恢复错误 - 自动重试
	L1Recoverable ErrorLevel = iota + 1
	// L2Intervention 需要人工干预
	L2Intervention
	// L3Fatal 致命错误 - 熔断告警
	L3Fatal
)

func (l ErrorLevel) String() string {
	switch l {
	case L1Recoverable:
		return "L1_RECOVERABLE"
	case L2Intervention:
		return "L2_INTERVENTION"
	case L3Fatal:
		return "L3_FATAL"
	default:
		return "UNKNOWN"
	}
}

// 预定义错误类型
var (
	ErrRateLimited      = errors.New("rate limited")
	ErrValidationFailed = errors.New("validation failed")
	ErrHallucination    = errors.New("LLM hallucination detected")
	ErrConfigInvalid    = errors.New("invalid configuration")
	ErrAuthFailed       = errors.New("authentication failed")
	ErrCacheUnavailable = errors.New("cache unavailable")
	ErrLLMUnavailable   = errors.New("LLM service unavailable")
	ErrToolFailed       = errors.New("tool execution failed")
)

// ClassifiedError 分类后的错误
type ClassifiedError struct {
	Level      ErrorLevel
	Code       string
	Message    string
	Cause      error
	Retryable  bool
	MaxRetries int
	Metadata   map[string]interface{}
}

func (e *ClassifiedError) Error() string {
	if e.Cause != nil {
		return e.Message + ": " + e.Cause.Error()
	}
	return e.Message
}

func (e *ClassifiedError) Unwrap() error {
	return e.Cause
}

// ClassifyError 对错误进行分类
func ClassifyError(err error) *ClassifiedError {
	if err == nil {
		return nil
	}

	// 检查是否已经是 ClassifiedError
	var classifiedErr *ClassifiedError
	if errors.As(err, &classifiedErr) {
		return classifiedErr
	}

	switch {
	case errors.Is(err, context.DeadlineExceeded):
		return &ClassifiedError{
			Level:      L1Recoverable,
			Code:       "TIMEOUT",
			Message:    "Operation timed out",
			Cause:      err,
			Retryable:  true,
			MaxRetries: 3,
		}

	case errors.Is(err, ErrRateLimited):
		return &ClassifiedError{
			Level:      L1Recoverable,
			Code:       "RATE_LIMITED",
			Message:    "Rate limit exceeded",
			Cause:      err,
			Retryable:  true,
			MaxRetries: 5,
			Metadata:   map[string]interface{}{"backoff": "exponential"},
		}

	case errors.Is(err, ErrCacheUnavailable):
		return &ClassifiedError{
			Level:      L1Recoverable,
			Code:       "CACHE_UNAVAILABLE",
			Message:    "Cache service unavailable",
			Cause:      err,
			Retryable:  true,
			MaxRetries: 3,
		}

	case errors.Is(err, ErrValidationFailed):
		return &ClassifiedError{
			Level:     L2Intervention,
			Code:      "VALIDATION_FAILED",
			Message:   "Data validation failed",
			Cause:     err,
			Retryable: false,
		}

	case errors.Is(err, ErrHallucination):
		return &ClassifiedError{
			Level:      L2Intervention,
			Code:       "LLM_HALLUCINATION",
			Message:    "LLM output verification failed",
			Cause:      err,
			Retryable:  true,
			MaxRetries: 2,
			Metadata:   map[string]interface{}{"require_human_review": true},
		}

	case errors.Is(err, ErrLLMUnavailable):
		return &ClassifiedError{
			Level:      L1Recoverable,
			Code:       "LLM_UNAVAILABLE",
			Message:    "LLM service unavailable",
			Cause:      err,
			Retryable:  true,
			MaxRetries: 3,
			Metadata:   map[string]interface{}{"try_fallback": true},
		}

	case errors.Is(err, ErrToolFailed):
		return &ClassifiedError{
			Level:      L1Recoverable,
			Code:       "TOOL_FAILED",
			Message:    "Tool execution failed",
			Cause:      err,
			Retryable:  true,
			MaxRetries: 2,
		}

	case errors.Is(err, ErrConfigInvalid), errors.Is(err, ErrAuthFailed):
		return &ClassifiedError{
			Level:     L3Fatal,
			Code:      "FATAL_CONFIG",
			Message:   "Fatal configuration or authentication error",
			Cause:     err,
			Retryable: false,
		}

	default:
		return &ClassifiedError{
			Level:      L1Recoverable,
			Code:       "UNKNOWN",
			Message:    "Unknown error",
			Cause:      err,
			Retryable:  true,
			MaxRetries: 1,
		}
	}
}

// NewClassifiedError 创建分类错误
func NewClassifiedError(level ErrorLevel, code, message string, cause error) *ClassifiedError {
	return &ClassifiedError{
		Level:   level,
		Code:    code,
		Message: message,
		Cause:   cause,
	}
}

// WrapWithLevel 包装错误并指定级别
func WrapWithLevel(err error, level ErrorLevel, message string) *ClassifiedError {
	classified := ClassifyError(err)
	classified.Level = level
	if message != "" {
		classified.Message = message
	}
	return classified
}

