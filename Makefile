# BioValue-AI Makefile
# 项目构建和部署自动化

.PHONY: all build test clean docker-build docker-push deploy proto help

# 变量
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
REGISTRY ?= ghcr.io/biovalue-ai
GO_WORKER_IMAGE = $(REGISTRY)/go-worker
LLM_BRIDGE_IMAGE = $(REGISTRY)/llm-bridge

# Go 相关
GO = go
GOFLAGS = -ldflags "-s -w -X main.Version=$(VERSION)"
GO_PACKAGES = ./...

# Python 相关
PYTHON = python3
PIP = pip3

# Proto 相关
PROTO_DIR = proto
GO_PROTO_OUT = proto
PYTHON_PROTO_OUT = proto

# 默认目标
all: build

# ============== 构建 ==============

## build: 构建所有组件
build: build-go build-python

## build-go: 构建 Go Worker
build-go:
	@echo "Building Go Worker..."
	$(GO) build $(GOFLAGS) -o bin/worker ./cmd/worker

## build-python: 安装 Python 依赖
build-python:
	@echo "Installing Python dependencies..."
	$(PIP) install -r requirements.txt

## proto: 生成 Proto 代码
proto:
	@echo "Generating Proto code..."
	# Go
	protoc --go_out=$(GO_PROTO_OUT) --go-grpc_out=$(GO_PROTO_OUT) \
		-I$(PROTO_DIR) $(PROTO_DIR)/*.proto
	# Python
	$(PYTHON) -m grpc_tools.protoc \
		-I$(PROTO_DIR) \
		--python_out=$(PYTHON_PROTO_OUT) \
		--grpc_python_out=$(PYTHON_PROTO_OUT) \
		$(PROTO_DIR)/*.proto

# ============== 测试 ==============

## test: 运行所有测试
test: test-go test-python

## test-go: 运行 Go 测试
test-go:
	@echo "Running Go tests..."
	$(GO) test -v -race -coverprofile=coverage.out $(GO_PACKAGES)
	$(GO) tool cover -func=coverage.out

## test-python: 运行 Python 测试
test-python:
	@echo "Running Python tests..."
	$(PYTHON) -m pytest tests/ -v --cov=llm_bridge --cov-report=term-missing

## lint: 运行代码检查
lint: lint-go lint-python

## lint-go: Go 代码检查
lint-go:
	@echo "Linting Go code..."
	golangci-lint run ./...

## lint-python: Python 代码检查
lint-python:
	@echo "Linting Python code..."
	ruff check llm_bridge/
	mypy llm_bridge/

# ============== Docker ==============

## docker-build: 构建 Docker 镜像
docker-build:
	@echo "Building Docker images..."
	docker build -t $(GO_WORKER_IMAGE):$(VERSION) -f build/Dockerfile.go-worker .
	docker build -t $(LLM_BRIDGE_IMAGE):$(VERSION) -f build/Dockerfile.llm-bridge .
	docker tag $(GO_WORKER_IMAGE):$(VERSION) $(GO_WORKER_IMAGE):latest
	docker tag $(LLM_BRIDGE_IMAGE):$(VERSION) $(LLM_BRIDGE_IMAGE):latest

## docker-push: 推送 Docker 镜像
docker-push:
	@echo "Pushing Docker images..."
	docker push $(GO_WORKER_IMAGE):$(VERSION)
	docker push $(GO_WORKER_IMAGE):latest
	docker push $(LLM_BRIDGE_IMAGE):$(VERSION)
	docker push $(LLM_BRIDGE_IMAGE):latest

# ============== 本地开发 ==============

## dev-up: 启动本地开发环境
dev-up:
	@echo "Starting local development environment..."
	docker-compose up -d

## dev-down: 停止本地开发环境
dev-down:
	@echo "Stopping local development environment..."
	docker-compose down

## dev-logs: 查看日志
dev-logs:
	docker-compose logs -f

## run-worker: 运行 Go Worker (本地)
run-worker:
	@echo "Running Go Worker..."
	$(GO) run ./cmd/worker --config=config/config.dev.yaml

## run-llm-bridge: 运行 LLM Bridge (本地)
run-llm-bridge:
	@echo "Running LLM Bridge..."
	$(PYTHON) -m llm_bridge.server --config=config/config.dev.yaml

# ============== 部署 ==============

## deploy-staging: 部署到 Staging
deploy-staging:
	@echo "Deploying to Staging..."
	kubectl apply -k deploy/k8s/overlays/staging

## deploy-production: 部署到 Production
deploy-production:
	@echo "Deploying to Production..."
	kubectl apply -k deploy/k8s/overlays/production

## deploy-k8s: 部署 K8s 基础资源
deploy-k8s:
	@echo "Deploying K8s resources..."
	kubectl apply -f deploy/k8s/namespace.yaml
	kubectl apply -f deploy/k8s/configmap.yaml
	kubectl apply -f deploy/k8s/worker-deployment.yaml
	kubectl apply -f deploy/k8s/llm-bridge-deployment.yaml

## rollback: 回滚部署
rollback:
	@echo "Rolling back deployment..."
	kubectl rollout undo deployment/biovalue-worker -n biovalue
	kubectl rollout undo deployment/llm-bridge -n biovalue

# ============== 清理 ==============

## clean: 清理构建产物
clean:
	@echo "Cleaning..."
	rm -rf bin/
	rm -rf coverage.out
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf *.egg-info
	find . -name "*.pyc" -delete

## clean-docker: 清理 Docker 镜像
clean-docker:
	docker rmi $(GO_WORKER_IMAGE):$(VERSION) || true
	docker rmi $(LLM_BRIDGE_IMAGE):$(VERSION) || true

# ============== 工具 ==============

## install-tools: 安装开发工具
install-tools:
	@echo "Installing development tools..."
	go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
	go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
	go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
	$(PIP) install ruff mypy pytest pytest-cov grpcio-tools

## fmt: 格式化代码
fmt:
	@echo "Formatting code..."
	$(GO) fmt $(GO_PACKAGES)
	ruff format llm_bridge/

## mod-tidy: 整理 Go 模块
mod-tidy:
	$(GO) mod tidy

# ============== 帮助 ==============

## help: 显示帮助信息
help:
	@echo "BioValue-AI Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make <target>"
	@echo ""
	@echo "Targets:"
	@grep -E '^##' $(MAKEFILE_LIST) | sed 's/## /  /'

