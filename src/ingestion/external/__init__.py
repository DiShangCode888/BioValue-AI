# 外部 API 模块
from .clinical_trials import ClinicalTrialsAPI
from .base import ExternalAPIClient

__all__ = ["ClinicalTrialsAPI", "ExternalAPIClient"]

