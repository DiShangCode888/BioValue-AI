# BioValue-AI API 参考手册

## 概述

BioValue-AI 是一个基于 LangGraph 架构的创新药全要素知识图谱智能投资分析平台。

**基础 URL**: `http://localhost:8000/api/v1`

**API 文档**: `http://localhost:8000/docs` (Swagger UI)

---

## 认证

当前版本不需要认证。后续版本将支持 API Key 认证。

---

## 图谱操作 API

### 创建节点

**POST** `/graph/nodes`

创建知识图谱节点。

**请求体:**

```json
{
  "node_type": "Drug",
  "data": {
    "name": "Pembrolizumab",
    "molecule_type": "单抗",
    "target": "PD-1",
    "moa": "PD-1抑制剂"
  }
}
```

**支持的节点类型:**

| 类型 | 说明 | 必填字段 |
|------|------|---------|
| `Company` | 公司 | name |
| `Drug` | 药物 | name, molecule_type, target, moa |
| `Indication` | 适应症 | name |
| `Trial` | 临床试验 | nct_id, title, design, phase, status |
| `EndpointData` | 终点数据 | trial_id |

**响应:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "node_type": "Drug",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Pembrolizumab",
    "molecule_type": "单抗",
    "target": "PD-1",
    "moa": "PD-1抑制剂",
    "created_at": "2024-01-15T10:30:00"
  }
}
```

---

### 获取节点

**GET** `/graph/nodes/{node_id}`

**参数:**
- `node_id` (path): 节点ID
- `node_type` (query, 可选): 节点类型

**响应:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "node_type": "Drug",
  "data": { ... }
}
```

---

### 列出节点

**GET** `/graph/nodes`

**参数:**
- `node_type` (query, 必填): 节点类型
- `limit` (query, 默认100): 返回数量
- `skip` (query, 默认0): 跳过数量

---

### 删除节点

**DELETE** `/graph/nodes/{node_id}`

---

### 创建关联

**POST** `/graph/edges`

**请求体:**

```json
{
  "edge_type": "TREATS",
  "source_id": "drug_001",
  "target_id": "indication_001",
  "data": {
    "treatment_line": "1L",
    "priority": 8
  }
}
```

**支持的关联类型:**

| 类型 | 说明 | 方向 |
|------|------|------|
| `TREATS` | 治疗关系 | Drug → Indication |
| `OUTPUTS` | 产出数据 | Trial → EndpointData |
| `COMBINED_WITH` | 联合用药 | Drug ↔ Drug |
| `HAS_SOC` | 标准疗法 | Indication → Drug |

---

### 执行 Cypher 查询

**POST** `/graph/query`

**请求体:**

```json
{
  "query": "MATCH (d:Drug)-[:TREATS]->(i:Indication) WHERE i.name = $indication RETURN d",
  "parameters": {
    "indication": "非小细胞肺癌"
  }
}
```

**响应:**

```json
{
  "results": [...],
  "count": 10
}
```

---

### 获取统计信息

**GET** `/graph/statistics`

**响应:**

```json
{
  "nodes": {
    "Drug": 150,
    "Company": 50,
    "Indication": 80
  },
  "edges": {
    "TREATS": 200,
    "COMBINED_WITH": 50
  }
}
```

---

## 数据摄入 API

### 爬取网页

**POST** `/data/crawl`

**请求体:**

```json
{
  "url": "https://example.com/drug-info",
  "extract_links": true,
  "max_pages": 1
}
```

---

### 解析文档

**POST** `/data/parse/document`

上传 PDF/DOCX/TXT 文件进行解析。

**请求:**
- Content-Type: `multipart/form-data`
- 字段: `file` (文件)

**响应:**

```json
{
  "filename": "clinical_report.pdf",
  "file_type": ".pdf",
  "text": "...",
  "pages": 10,
  "metadata": {...}
}
```

---

### 搜索临床试验

**POST** `/data/clinical-trials/search`

搜索 ClinicalTrials.gov 数据库。

**请求体:**

```json
{
  "query": "pembrolizumab",
  "condition": "非小细胞肺癌",
  "intervention": null,
  "status": ["RECRUITING", "ACTIVE_NOT_RECRUITING"],
  "phase": ["PHASE3"],
  "page_size": 20
}
```

---

### 导入临床试验

**POST** `/data/clinical-trials/import/{nct_id}`

将 ClinicalTrials.gov 的试验数据导入知识图谱。

---

## 分析 API

### 竞争坍缩模拟

**POST** `/analysis/competition`

当某药物在特定适应症实验失败时，分析对整个管线生态的影响。

**请求体:**

```json
{
  "failed_drug_id": "drug_001",
  "failed_indication_id": "indication_001",
  "include_llm_analysis": true
}
```

**响应:**

```json
{
  "failed_drug_name": "Drug A",
  "failed_indication_id": "indication_001",
  "impact_severity": "high",
  "total_affected_drugs": 5,
  "total_affected_trials": 8,
  "total_affected_companies": 3,
  "affected_combinations": [
    {
      "partner_drug_id": "drug_002",
      "partner_drug_name": "Drug B",
      "synergy_score": 7.5,
      "company": "Company X",
      "adjusted_success_rate": 0.15
    }
  ],
  "recommendations": [
    "建议重新评估 Drug B + Drug A 联合方案的投资",
    "关注 Company X 的管线调整动态"
  ],
  "analysis": "..."
}
```

---

### 空白点挖掘

**POST** `/analysis/opportunity`

发现高价值投资机会。

**请求体:**

```json
{
  "min_prevalence": 50000,
  "max_soc_score": 5.0,
  "min_unmet_need": 8.0,
  "include_llm_analysis": true
}
```

**响应:**

```json
{
  "total_opportunities": 15,
  "high_priority_count": 3,
  "medium_priority_count": 7,
  "low_priority_count": 5,
  "high_priority": [
    {
      "indication_id": "ind_001",
      "indication_name": "胆管癌",
      "prevalence": 80000,
      "unmet_need_score": 9.2,
      "investment_score": 85.5
    }
  ],
  "recommendations": [...],
  "analysis_summary": "..."
}
```

---

### 数据诚信检查

**POST** `/analysis/integrity`

识别可疑的临床数据。

**请求体:**

```json
{
  "p_value_threshold": 0.01,
  "censoring_threshold": 0.6,
  "include_llm_analysis": true
}
```

**响应:**

```json
{
  "total_checked": 100,
  "suspicious_count": 5,
  "critical_count": 1,
  "high_risk_count": 2,
  "medium_risk_count": 2,
  "suspicious_data": [
    {
      "trial_nct": "NCT12345678",
      "trial_phase": "Phase III",
      "hr_pfs": 0.92,
      "hr_pfs_p_value": 0.001,
      "censoring_density": 0.75,
      "risk_level": "HIGH_RISK",
      "concerns": [
        "HR接近1但p值极显著，可能存在样本量过大导致的统计学假阳性"
      ]
    }
  ],
  "recommendations": [...],
  "summary": "..."
}
```

---

## 工作流 API

### 运行完整工作流

**POST** `/workflow/run`

基于用户查询自动执行分析流程。

**请求体:**

```json
{
  "query": "分析 PD-1 抑制剂在非小细胞肺癌领域的竞争格局",
  "session_id": "session_001",
  "max_iterations": 10
}
```

**响应:**

```json
{
  "session_id": "session_001",
  "query": "...",
  "final_report": "...",
  "summary": "...",
  "completed_tasks": [...],
  "analysis_results": [...],
  "extracted_entities_count": 5,
  "created_nodes_count": 3
}
```

---

### 流式运行工作流

**POST** `/workflow/run/stream`

实时返回工作流执行状态。

返回 Server-Sent Events (SSE) 流。

---

### 数据提取

**POST** `/workflow/extract`

从文本中提取结构化实体。

**请求体:**

```json
{
  "text": "Pembrolizumab 是一种 PD-1 抑制剂...",
  "source": "clinical_report",
  "target_entities": ["Drug", "Company", "Trial"]
}
```

---

### 对话

**POST** `/workflow/chat`

基于知识图谱的问答对话。

**请求体:**

```json
{
  "message": "HER2阳性乳腺癌有哪些在研药物？",
  "session_id": "chat_001"
}
```

---

## Python SDK 使用示例

### 安装

```bash
pip install -e .
```

### 基本使用

```python
from biovalue import BioValueClient

# 创建客户端
client = BioValueClient(base_url="http://localhost:8000")

# 创建药物节点
drug = client.create_drug(
    name="Trastuzumab",
    molecule_type="单抗",
    target="HER2",
    moa="阻断HER2信号通路"
)
print(f"创建药物: {drug.name} (ID: {drug.id})")

# 创建适应症节点
indication = client.create_indication(
    name="HER2阳性乳腺癌",
    prevalence=300000,
    unmet_need_score=6.5
)

# 创建治疗关系
edge_id = client.create_treats_relation(
    drug_id=drug.id,
    indication_id=indication.id,
    treatment_line="1L",
    priority=9
)

# 竞争分析
result = client.analyze_competition(
    failed_drug_id=drug.id,
    failed_indication_id=indication.id
)
print(f"影响严重程度: {result.impact_severity}")
for rec in result.recommendations:
    print(f"  - {rec}")

# 空白点挖掘
opportunities = client.discover_opportunities(
    min_prevalence=50000,
    min_unmet_need=8.0
)
print(f"发现 {opportunities.total_opportunities} 个投资机会")
for opp in opportunities.high_priority:
    print(f"  - {opp.indication_name}: {opp.investment_score:.1f}")

# 数据诚信检查
integrity = client.check_integrity(
    p_value_threshold=0.01,
    censoring_threshold=0.6
)
print(f"可疑数据: {integrity.suspicious_count} 条")

# 对话
response = client.chat("HER2阳性乳腺癌的一线治疗标准是什么？")
print(response.response)

# 关闭客户端
client.close()
```

### 使用 Context Manager

```python
from biovalue import BioValueClient

with BioValueClient() as client:
    result = client.analyze_competition("drug_001", "ind_001")
    print(result.summary)
```

---

## 错误处理

所有 API 错误返回统一格式:

```json
{
  "detail": "错误描述"
}
```

**常见错误码:**

| 状态码 | 说明 |
|--------|------|
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 健康检查

**GET** `/health`

```json
{
  "status": "healthy",
  "services": {
    "neo4j": {
      "status": "connected",
      "nodes": 500,
      "edges": 800
    }
  }
}
```

