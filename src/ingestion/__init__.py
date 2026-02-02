# 数据摄入模块
"""
多源数据摄入支持:
- 爬虫: 从网页抓取数据
- 文档解析: 解析 PDF/DOCX 等文档
- 外部 API: 对接 ClinicalTrials.gov 等
- 手动录入: 结构化数据导入
"""

from .crawler import WebCrawler
from .parser import DocumentParser
from .external import ClinicalTrialsAPI, ExternalAPIClient

__all__ = [
    "WebCrawler",
    "DocumentParser",
    "ClinicalTrialsAPI",
    "ExternalAPIClient",
]

