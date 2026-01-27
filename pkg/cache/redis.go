// Redis 缓存实现
package cache

import (
	"context"
	"fmt"
	"time"

	"github.com/biovalue-ai/biovalue/pkg/config"
	"github.com/go-redis/redis/v8"
)

// RedisCache Redis 缓存客户端
type RedisCache struct {
	client *redis.Client
}

// NewRedisCache 创建 Redis 缓存客户端
func NewRedisCache(cfg config.RedisConfig) (*RedisCache, error) {
	client := redis.NewClient(&redis.Options{
		Addr:         cfg.Address,
		Password:     cfg.Password,
		DB:           cfg.DB,
		PoolSize:     cfg.PoolSize,
		MinIdleConns: cfg.MinIdleConns,
		DialTimeout:  cfg.DialTimeout,
		ReadTimeout:  cfg.ReadTimeout,
		WriteTimeout: cfg.WriteTimeout,
	})

	// 测试连接
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	return &RedisCache{client: client}, nil
}

// Get 获取缓存
func (r *RedisCache) Get(ctx context.Context, key string) (string, error) {
	result, err := r.client.Get(ctx, key).Result()
	if err == redis.Nil {
		return "", nil
	}
	return result, err
}

// Set 设置缓存
func (r *RedisCache) Set(ctx context.Context, key, value string, ttl time.Duration) error {
	return r.client.Set(ctx, key, value, ttl).Err()
}

// Delete 删除缓存
func (r *RedisCache) Delete(ctx context.Context, key string) error {
	return r.client.Del(ctx, key).Err()
}

// Exists 检查键是否存在
func (r *RedisCache) Exists(ctx context.Context, key string) (bool, error) {
	result, err := r.client.Exists(ctx, key).Result()
	return result > 0, err
}

// SetNX 设置缓存（仅当不存在时）
func (r *RedisCache) SetNX(ctx context.Context, key, value string, ttl time.Duration) (bool, error) {
	return r.client.SetNX(ctx, key, value, ttl).Result()
}

// Expire 设置过期时间
func (r *RedisCache) Expire(ctx context.Context, key string, ttl time.Duration) error {
	return r.client.Expire(ctx, key, ttl).Err()
}

// TTL 获取剩余过期时间
func (r *RedisCache) TTL(ctx context.Context, key string) (time.Duration, error) {
	return r.client.TTL(ctx, key).Result()
}

// HGet 获取 Hash 字段
func (r *RedisCache) HGet(ctx context.Context, key, field string) (string, error) {
	result, err := r.client.HGet(ctx, key, field).Result()
	if err == redis.Nil {
		return "", nil
	}
	return result, err
}

// HSet 设置 Hash 字段
func (r *RedisCache) HSet(ctx context.Context, key string, values ...interface{}) error {
	return r.client.HSet(ctx, key, values...).Err()
}

// HGetAll 获取所有 Hash 字段
func (r *RedisCache) HGetAll(ctx context.Context, key string) (map[string]string, error) {
	return r.client.HGetAll(ctx, key).Result()
}

// XAdd 添加到 Stream
func (r *RedisCache) XAdd(ctx context.Context, stream string, values map[string]interface{}) (string, error) {
	return r.client.XAdd(ctx, &redis.XAddArgs{
		Stream: stream,
		Values: values,
	}).Result()
}

// XRead 从 Stream 读取
func (r *RedisCache) XRead(ctx context.Context, stream string, count int64, block time.Duration) ([]redis.XStream, error) {
	return r.client.XRead(ctx, &redis.XReadArgs{
		Streams: []string{stream, "0"},
		Count:   count,
		Block:   block,
	}).Result()
}

// XLen 获取 Stream 长度
func (r *RedisCache) XLen(ctx context.Context, stream string) (int64, error) {
	return r.client.XLen(ctx, stream).Result()
}

// Close 关闭连接
func (r *RedisCache) Close() error {
	return r.client.Close()
}

// Client 获取原始 Redis 客户端
func (r *RedisCache) Client() *redis.Client {
	return r.client
}

