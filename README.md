# BioValue-AI 创新药知识图谱系统

基于 LangGraph 架构的创新药全要素知识图谱智能投资分析平台。

## 功能特性

- **知识图谱构建**: 基于 Neo4j 的创新药全要素知识图谱
- **多源数据摄入**: 支持爬虫、文档解析、外部 API 等多种数据源
- **LLM 智能分析**: 解耦设计，支持 OpenAI/DeepSeek/通义千问等多种模型
- **投资决策支持**: 竞争坍缩模拟、空白点挖掘、数据诚信预警

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         客户端层                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│  │  Web UI  │  │   SDK    │  │   CLI    │                      │
│  └──────────┘  └──────────┘  └──────────┘                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                       API 层 (FastAPI)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Graph   │  │   Data   │  │ Analysis │  │ Workflow │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                   LangGraph Agent 核心                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │ Coordinator│──│  Extractor │──│  Analyzer  │                │
│  └────────────┘  └────────────┘  └────────────┘                │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                        存储层                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│  │  Neo4j   │  │ VectorDB │  │  Redis   │                      │
│  └──────────┘  └──────────┘  └──────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd BioValue-AI

# 安装依赖 (推荐使用 uv)
uv pip install -e .

# 或使用 pip
pip install -e .
```

### 2. 配置

```bash
# 复制配置文件
cp conf.yaml.example conf.yaml

# 编辑配置，填入 API Keys 等信息
vim conf.yaml
```

### 3. 启动服务

```bash
# 使用 Docker Compose 启动所有服务
cd docker
docker-compose up -d

# 或单独启动 API 服务
uvicorn src.api.main:app --reload
```

### 4. 访问服务

- API 文档: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474

## 知识图谱数据模型

### 节点类型

| 节点类型 | 核心属性 |
|---------|---------|
| Company (公司) | 现金余额、融资轮次、研发费用占比、科学家背景评分 |
| Drug (药物) | 分子类型、靶点、作用机制、专利失效日、给药方式 |
| Indication (适应症) | 流行病学数据、标准疗法、未满足需求程度 |
| Trial (临床实验) | NCT编号、实验设计、入组人数、治疗线数、状态 |
| Data (终点数据) | mPFS、mOS、ORR、HR、p值、不良反应率 |
| Asset (媒体资源) | KM曲线URL、财报PDF、FDA审议函链接 |
| External (外部因素) | 医保状态、集采压力、KOL评价指数 |

### 关联类型

- `TREATS`: 药物 → 适应症 (治疗线数、优先级、渗透率)
- `OUTPUTS`: 临床实验 → 终点数据 (发布日期、阶段、拖尾效应)
- `COMBINED_WITH`: 药物 → 药物 (协同效应、联合实验)
- `HAS_SOC`: 适应症 → 药物 (标准疗法基准)

## API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/graph/nodes` | POST | 创建节点 |
| `/api/v1/graph/edges` | POST | 创建关联 |
| `/api/v1/graph/query` | POST | Cypher 查询 |
| `/api/v1/analysis/competition` | POST | 竞争坍缩模拟 |
| `/api/v1/analysis/opportunity` | POST | 空白点挖掘 |
| `/api/v1/workflow/extract` | POST | LLM 数据提取 |

## Python SDK 使用

```python
from biovalue import BioValueClient

client = BioValueClient(base_url="http://localhost:8000")

# 创建药物节点
drug = client.create_drug(
    name="Trastuzumab",
    molecule_type="单抗",
    target="HER2",
    moa="阻断 HER2 信号通路"
)

# 竞争分析
result = client.analyze_competition(
    drug_id=drug.id,
    indication="乳腺癌"
)
print(result.affected_combos)
```

## 开发

```bash
# 安装开发依赖
uv pip install -e ".[dev]"

# 运行测试
pytest

# 代码格式化
ruff format src/
ruff check src/ --fix
```

## 技术栈

- **框架**: FastAPI + LangGraph + LangChain
- **图数据库**: Neo4j
- **向量数据库**: ChromaDB
- **缓存**: Redis
- **LLM**: OpenAI / DeepSeek / 通义千问 (可配置)

## License

MIT

