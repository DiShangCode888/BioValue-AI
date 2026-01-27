// 配置管理
package config

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/spf13/viper"
)

// Config 主配置结构
type Config struct {
	System        SystemConfig        `mapstructure:"system"`
	Temporal      TemporalConfig      `mapstructure:"temporal"`
	Storage       StorageConfig       `mapstructure:"storage"`
	LLM           LLMConfig           `mapstructure:"llm"`
	MCP           MCPConfig           `mapstructure:"mcp"`
	Observability ObservabilityConfig `mapstructure:"observability"`
	Security      SecurityConfig      `mapstructure:"security"`
}

// SystemConfig 系统配置
type SystemConfig struct {
	Env             string        `mapstructure:"env"`
	ServiceName     string        `mapstructure:"service_name"`
	Version         string        `mapstructure:"version"`
	MaxConcurrency  int           `mapstructure:"max_concurrency"`
	ShutdownTimeout time.Duration `mapstructure:"shutdown_timeout"`
}

// TemporalConfig Temporal 配置
type TemporalConfig struct {
	Address   string       `mapstructure:"address"`
	Namespace string       `mapstructure:"namespace"`
	TaskQueue string       `mapstructure:"task_queue"`
	Worker    WorkerConfig `mapstructure:"worker"`
	Retry     RetryConfig  `mapstructure:"retry"`
}

// WorkerConfig Worker 配置
type WorkerConfig struct {
	MaxConcurrentActivities  int           `mapstructure:"max_concurrent_activities"`
	MaxConcurrentWorkflows   int           `mapstructure:"max_concurrent_workflows"`
	ActivityPollInterval     time.Duration `mapstructure:"activity_poll_interval"`
}

// RetryConfig 重试配置
type RetryConfig struct {
	InitialInterval    time.Duration `mapstructure:"initial_interval"`
	BackoffCoefficient float64       `mapstructure:"backoff_coefficient"`
	MaximumInterval    time.Duration `mapstructure:"maximum_interval"`
	MaximumAttempts    int           `mapstructure:"maximum_attempts"`
}

// StorageConfig 存储配置
type StorageConfig struct {
	Redis    RedisConfig    `mapstructure:"redis"`
	VectorDB VectorDBConfig `mapstructure:"vector_db"`
}

// RedisConfig Redis 配置
type RedisConfig struct {
	Address      string        `mapstructure:"address"`
	Password     string        `mapstructure:"password"`
	DB           int           `mapstructure:"db"`
	PoolSize     int           `mapstructure:"pool_size"`
	MinIdleConns int           `mapstructure:"min_idle_conns"`
	DialTimeout  time.Duration `mapstructure:"dial_timeout"`
	ReadTimeout  time.Duration `mapstructure:"read_timeout"`
	WriteTimeout time.Duration `mapstructure:"write_timeout"`
}

// VectorDBConfig 向量数据库配置
type VectorDBConfig struct {
	Type       string `mapstructure:"type"`
	Address    string `mapstructure:"address"`
	Collection string `mapstructure:"collection"`
	Dimension  int    `mapstructure:"dimension"`
	IndexType  string `mapstructure:"index_type"`
	MetricType string `mapstructure:"metric_type"`
}

// LLMConfig LLM 配置
type LLMConfig struct {
	Provider   string          `mapstructure:"provider"`
	Model      string          `mapstructure:"model"`
	APIKey     string          `mapstructure:"api_key"`
	BaseURL    string          `mapstructure:"base_url"`
	Timeout    time.Duration   `mapstructure:"timeout"`
	MaxRetries int             `mapstructure:"max_retries"`
	RateLimit  RateLimitConfig `mapstructure:"rate_limit"`
	Fallback   FallbackConfig  `mapstructure:"fallback"`
}

// RateLimitConfig 限速配置
type RateLimitConfig struct {
	RequestsPerMinute int `mapstructure:"requests_per_minute"`
	TokensPerMinute   int `mapstructure:"tokens_per_minute"`
}

// FallbackConfig 降级配置
type FallbackConfig struct {
	Enabled  bool   `mapstructure:"enabled"`
	Provider string `mapstructure:"provider"`
	Model    string `mapstructure:"model"`
	APIKey   string `mapstructure:"api_key"`
}

// MCPConfig MCP 配置
type MCPConfig struct {
	Discovery DiscoveryConfig   `mapstructure:"discovery"`
	Servers   []MCPServerConfig `mapstructure:"servers"`
}

// DiscoveryConfig 服务发现配置
type DiscoveryConfig struct {
	Type string `mapstructure:"type"`
}

// MCPServerConfig MCP 服务器配置
type MCPServerConfig struct {
	ID      string            `mapstructure:"id"`
	Type    string            `mapstructure:"type"`
	Command string            `mapstructure:"command"`
	Args    []string          `mapstructure:"args"`
	Address string            `mapstructure:"address"`
	Timeout time.Duration     `mapstructure:"timeout"`
	Env     map[string]string `mapstructure:"env"`
}

// ObservabilityConfig 可观测性配置
type ObservabilityConfig struct {
	Tracing TracingConfig `mapstructure:"tracing"`
	Metrics MetricsConfig `mapstructure:"metrics"`
	Logging LoggingConfig `mapstructure:"logging"`
}

// TracingConfig 追踪配置
type TracingConfig struct {
	Enabled    bool    `mapstructure:"enabled"`
	Exporter   string  `mapstructure:"exporter"`
	Endpoint   string  `mapstructure:"endpoint"`
	SampleRate float64 `mapstructure:"sample_rate"`
}

// MetricsConfig 指标配置
type MetricsConfig struct {
	Enabled bool   `mapstructure:"enabled"`
	Port    int    `mapstructure:"port"`
	Path    string `mapstructure:"path"`
}

// LoggingConfig 日志配置
type LoggingConfig struct {
	Level  string `mapstructure:"level"`
	Format string `mapstructure:"format"`
	Output string `mapstructure:"output"`
}

// SecurityConfig 安全配置
type SecurityConfig struct {
	TLS   TLSConfig   `mapstructure:"tls"`
	Vault VaultConfig `mapstructure:"vault"`
	Audit AuditConfig `mapstructure:"audit"`
}

// TLSConfig TLS 配置
type TLSConfig struct {
	Enabled  bool   `mapstructure:"enabled"`
	CertFile string `mapstructure:"cert_file"`
	KeyFile  string `mapstructure:"key_file"`
	CAFile   string `mapstructure:"ca_file"`
}

// VaultConfig Vault 配置
type VaultConfig struct {
	Enabled    bool   `mapstructure:"enabled"`
	Address    string `mapstructure:"address"`
	AuthMethod string `mapstructure:"auth_method"`
	MountPath  string `mapstructure:"mount_path"`
}

// AuditConfig 审计配置
type AuditConfig struct {
	Enabled    bool   `mapstructure:"enabled"`
	Storage    string `mapstructure:"storage"`
	Bucket     string `mapstructure:"bucket"`
	Encryption bool   `mapstructure:"encryption"`
}

// Load 加载配置
func Load() (*Config, error) {
	// 确定配置文件路径
	configPath := os.Getenv("CONFIG_PATH")
	if configPath == "" {
		configPath = "config/config.yaml"
	}

	viper.SetConfigFile(configPath)
	viper.SetConfigType("yaml")

	// 环境变量替换
	viper.AutomaticEnv()
	viper.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))

	if err := viper.ReadInConfig(); err != nil {
		return nil, fmt.Errorf("failed to read config: %w", err)
	}

	var config Config
	if err := viper.Unmarshal(&config); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}

	// 处理环境变量中的密钥
	config.LLM.APIKey = os.ExpandEnv(config.LLM.APIKey)
	config.LLM.Fallback.APIKey = os.ExpandEnv(config.LLM.Fallback.APIKey)
	config.Storage.Redis.Password = os.ExpandEnv(config.Storage.Redis.Password)

	// 设置默认值
	setDefaults(&config)

	return &config, nil
}

func setDefaults(cfg *Config) {
	if cfg.System.MaxConcurrency == 0 {
		cfg.System.MaxConcurrency = 50
	}
	if cfg.System.ShutdownTimeout == 0 {
		cfg.System.ShutdownTimeout = 30 * time.Second
	}
	if cfg.Temporal.Worker.MaxConcurrentActivities == 0 {
		cfg.Temporal.Worker.MaxConcurrentActivities = 20
	}
	if cfg.Temporal.Worker.MaxConcurrentWorkflows == 0 {
		cfg.Temporal.Worker.MaxConcurrentWorkflows = 10
	}
	if cfg.Storage.Redis.PoolSize == 0 {
		cfg.Storage.Redis.PoolSize = 100
	}
	if cfg.LLM.Timeout == 0 {
		cfg.LLM.Timeout = 120 * time.Second
	}
	if cfg.Observability.Metrics.Port == 0 {
		cfg.Observability.Metrics.Port = 9090
	}
}

