# BioValue-AI Python SDK
"""
BioValue-AI 创新药知识图谱系统 Python SDK

使用示例:

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

# 竞争分析
result = client.analyze_competition(
    drug_id=drug.id,
    indication_id="breast_cancer_001"
)
print(result.recommendations)

# 空白点挖掘
opportunities = client.discover_opportunities(
    min_prevalence=50000,
    min_unmet_need=8.0
)
for opp in opportunities.high_priority:
    print(f"{opp.indication_name}: {opp.investment_score}")
```
"""

from .client import BioValueClient
from .models import (
    Drug,
    Company,
    Indication,
    Trial,
    EndpointData,
    CompetitionAnalysisResult,
    OpportunityResult,
    IntegrityCheckResult,
)

__version__ = "0.1.0"
__all__ = [
    "BioValueClient",
    "Drug",
    "Company",
    "Indication",
    "Trial",
    "EndpointData",
    "CompetitionAnalysisResult",
    "OpportunityResult",
    "IntegrityCheckResult",
]

