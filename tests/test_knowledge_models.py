# 知识图谱模型测试
"""
测试知识图谱节点和边模型
"""

import pytest
from datetime import date

from src.knowledge.models.nodes import (
    Drug,
    Company,
    Indication,
    Trial,
    EndpointData,
    MoleculeType,
    TrialDesign,
    TrialPhase,
    TrialStatus,
)
from src.knowledge.models.edges import (
    TreatsRelation,
    CombinedWithRelation,
    OutputsRelation,
)


class TestDrugModel:
    """药物模型测试"""
    
    def test_create_drug(self):
        """测试创建药物"""
        drug = Drug(
            name="Pembrolizumab",
            molecule_type=MoleculeType.MONOCLONAL,
            target="PD-1",
            moa="PD-1抑制剂",
        )
        
        assert drug.name == "Pembrolizumab"
        assert drug.molecule_type == MoleculeType.MONOCLONAL
        assert drug.target == "PD-1"
        assert drug.id is not None
    
    def test_drug_to_neo4j(self):
        """测试转换为 Neo4j 属性"""
        drug = Drug(
            name="Trastuzumab",
            molecule_type=MoleculeType.MONOCLONAL,
            target="HER2",
            moa="HER2阻断",
            loe_date=date(2025, 12, 31),
        )
        
        props = drug.to_neo4j_properties()
        
        assert props["name"] == "Trastuzumab"
        assert props["molecule_type"] == "单抗"
        assert props["loe_date"] == "2025-12-31"


class TestCompanyModel:
    """公司模型测试"""
    
    def test_create_company(self):
        """测试创建公司"""
        company = Company(
            name="Merck",
            cash_balance=10.5,
            rd_expense_ratio=0.25,
            scientist_background_score=8.5,
        )
        
        assert company.name == "Merck"
        assert company.cash_balance == 10.5
        assert company.rd_expense_ratio == 0.25


class TestIndicationModel:
    """适应症模型测试"""
    
    def test_create_indication(self):
        """测试创建适应症"""
        indication = Indication(
            name="非小细胞肺癌",
            prevalence=500000,
            current_soc="化疗",
            unmet_need_score=7.5,
        )
        
        assert indication.name == "非小细胞肺癌"
        assert indication.prevalence == 500000
        assert indication.unmet_need_score == 7.5


class TestTrialModel:
    """临床试验模型测试"""
    
    def test_create_trial(self):
        """测试创建临床试验"""
        trial = Trial(
            nct_id="NCT12345678",
            title="Test Trial",
            design=TrialDesign.DOUBLE_BLIND,
            phase=TrialPhase.PHASE_3,
            status=TrialStatus.RECRUITING,
            enrollment_target=500,
        )
        
        assert trial.nct_id == "NCT12345678"
        assert trial.design == TrialDesign.DOUBLE_BLIND
        assert trial.phase == TrialPhase.PHASE_3


class TestEndpointDataModel:
    """终点数据模型测试"""
    
    def test_create_endpoint_data(self):
        """测试创建终点数据"""
        data = EndpointData(
            trial_id="trial_001",
            mpfs_months=12.5,
            mos_months=24.0,
            orr_percent=45.5,
            hr_pfs=0.65,
            hr_pfs_p_value=0.001,
            grade3_plus_ae_rate=25.0,
        )
        
        assert data.mpfs_months == 12.5
        assert data.hr_pfs == 0.65
        assert data.grade3_plus_ae_rate == 25.0


class TestEdgeModels:
    """边模型测试"""
    
    def test_treats_relation(self):
        """测试治疗关系"""
        rel = TreatsRelation(
            source_id="drug_001",
            target_id="indication_001",
            treatment_line="1L",
            priority=8,
            market_penetration_estimate=0.3,
        )
        
        assert rel.source_id == "drug_001"
        assert rel.target_id == "indication_001"
        assert rel.treatment_line == "1L"
    
    def test_combined_with_relation(self):
        """测试联合用药关系"""
        rel = CombinedWithRelation(
            source_id="drug_001",
            target_id="drug_002",
            synergy_score=7.5,
            synergy_mechanism="互补靶点",
        )
        
        assert rel.synergy_score == 7.5
        assert rel.synergy_mechanism == "互补靶点"

