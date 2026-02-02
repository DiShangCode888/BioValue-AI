# Cypher 查询模板
"""
创新药知识图谱核心查询模板

基于投资分析场景设计:
1. 竞争坍缩模拟
2. 空白点挖掘  
3. 数据诚信预警
"""

# ==============================================================================
# 竞争坍缩模拟
# 如果药物X在适应症A的一线治疗实验中失败，图谱会自动沿路径找到所有
# 以药物X作为底层逻辑的联用方案，并调低它们的成功率期望
# ==============================================================================

COMPETITION_COLLAPSE_QUERY = """
// 竞争坍缩模拟：找出依赖失败药物的所有管线
// 参数: $failed_drug_id - 失败药物ID
//       $failed_indication_id - 失败的适应症ID

MATCH (failed:Drug {id: $failed_drug_id})

// 找出所有以该药物为基础的联合用药方案
OPTIONAL MATCH (failed)-[combo:COMBINED_WITH]-(partner:Drug)
OPTIONAL MATCH (failed)-[:PART_OF_COMBO]->(combo_node:ComboNode)

// 找出这些联合方案在该适应症的实验
OPTIONAL MATCH (partner)-[treats:TREATS]->(ind:Indication {id: $failed_indication_id})
OPTIONAL MATCH (partner)-[:DEVELOPED_BY]->(company:Company)
OPTIONAL MATCH (partner)<-[:OUTPUTS]-(trial:Trial)-[:OUTPUTS]->(endpoint:EndpointData)

RETURN {
    failed_drug: failed.name,
    affected_combinations: collect(DISTINCT {
        partner_drug: partner.name,
        partner_drug_id: partner.id,
        synergy_score: combo.synergy_score,
        combo_node: combo_node.name,
        company: company.name,
        treatment_line: treats.treatment_line,
        trial_nct: trial.nct_id,
        trial_phase: trial.phase,
        trial_status: trial.status
    }),
    impact_summary: {
        total_affected_drugs: count(DISTINCT partner),
        total_affected_trials: count(DISTINCT trial),
        total_affected_companies: count(DISTINCT company)
    }
} as collapse_analysis
"""

FIND_AFFECTED_COMBOS_QUERY = """
// 查找受影响的联合用药方案详情
// 参数: $drug_id - 药物ID

MATCH (d:Drug {id: $drug_id})-[:PART_OF_COMBO]->(combo:ComboNode)
MATCH (other:Drug)-[:PART_OF_COMBO]->(combo)
WHERE other.id <> $drug_id

OPTIONAL MATCH (combo)<-[:PART_OF_COMBO]-(all_drugs:Drug)
OPTIONAL MATCH (trial:Trial)-[:OUTPUTS]->(endpoint:EndpointData)
WHERE any(drug_id IN combo.drug_ids WHERE drug_id IN [trial.drug_id])

RETURN combo {
    .*,
    component_drugs: collect(DISTINCT all_drugs.name),
    related_trials: collect(DISTINCT {
        nct_id: trial.nct_id,
        phase: trial.phase,
        status: trial.status,
        orr: endpoint.orr_percent,
        mpfs: endpoint.mpfs_months
    })
} as combo_details
ORDER BY combo.synergy_score DESC
"""

# ==============================================================================
# 空白点挖掘
# 搜索"高流行病学数据 + 低SoC疗效 + 无在研Phase III管线"的适应症节点
# ==============================================================================

OPPORTUNITY_DISCOVERY_QUERY = """
// 空白点挖掘：寻找高价值投资机会
// 参数: $min_prevalence - 最小患病人数
//       $max_soc_score - 最大SoC疗效评分
//       $min_unmet_need - 最小未满足需求分数

MATCH (ind:Indication)
WHERE ind.prevalence >= $min_prevalence
  AND (ind.soc_efficacy_score IS NULL OR ind.soc_efficacy_score <= $max_soc_score)
  AND ind.unmet_need_score >= $min_unmet_need

// 检查是否有在研Phase III管线
OPTIONAL MATCH (drug:Drug)-[treats:TREATS]->(ind)
OPTIONAL MATCH (drug)<-[:OUTPUTS]-(trial:Trial)
WHERE trial.phase IN ['Phase III', 'Phase II/III']
  AND trial.status IN ['招募中', '进行中-不招募']

WITH ind, 
     collect(DISTINCT drug) as competing_drugs,
     collect(DISTINCT trial) as active_trials,
     count(DISTINCT trial) as phase3_count

// 筛选无活跃Phase III的适应症
WHERE phase3_count = 0

// 获取当前SoC信息
OPTIONAL MATCH (ind)-[soc_rel:HAS_SOC]->(soc_drug:Drug)
WHERE soc_rel.is_current_soc = true

RETURN {
    indication: ind {
        .id, .name, .prevalence, .incidence_annual,
        .unmet_need_score, .soc_efficacy_score,
        .market_size, .therapeutic_area
    },
    current_soc: soc_drug.name,
    soc_years: soc_rel.years_as_soc,
    competing_drugs_count: size(competing_drugs),
    investment_score: (ind.prevalence / 10000.0) * ind.unmet_need_score * 
                      (10 - coalesce(ind.soc_efficacy_score, 5))
} as opportunity

ORDER BY opportunity.investment_score DESC
LIMIT 20
"""

HIGH_UNMET_NEED_QUERY = """
// 查找高未满足需求的适应症
// 参数: $min_unmet_need_score - 最小未满足需求分数

MATCH (ind:Indication)
WHERE ind.unmet_need_score >= $min_unmet_need_score

// 统计各阶段管线数量
OPTIONAL MATCH (drug:Drug)-[:TREATS]->(ind)
OPTIONAL MATCH (drug)<-[:OUTPUTS]-(trial:Trial)

WITH ind,
     count(DISTINCT CASE WHEN trial.phase = 'Phase III' THEN trial END) as phase3_count,
     count(DISTINCT CASE WHEN trial.phase = 'Phase II' THEN trial END) as phase2_count,
     count(DISTINCT CASE WHEN trial.phase = 'Phase I' THEN trial END) as phase1_count,
     collect(DISTINCT drug.name) as drugs_in_development

RETURN ind {
    .id, .name, .unmet_need_score, .prevalence,
    .current_soc, .therapeutic_area
},
phase3_count, phase2_count, phase1_count,
drugs_in_development,
CASE 
    WHEN phase3_count = 0 AND ind.unmet_need_score >= 8 THEN 'HIGH_OPPORTUNITY'
    WHEN phase3_count <= 2 AND ind.unmet_need_score >= 7 THEN 'MEDIUM_OPPORTUNITY'
    ELSE 'LOW_OPPORTUNITY'
END as opportunity_level

ORDER BY ind.unmet_need_score DESC, phase3_count ASC
"""

# ==============================================================================
# 数据诚信预警
# 如果终点数据的p值极其显著，但KM曲线尾部有大量删失点，
# 图谱会自动触发"数据可靠性存疑"标签
# ==============================================================================

DATA_INTEGRITY_CHECK_QUERY = """
// 数据诚信检查：识别可疑的临床数据
// 参数: $p_value_threshold - p值阈值
//       $censoring_threshold - 删失密度阈值

MATCH (trial:Trial)-[out:OUTPUTS]->(endpoint:EndpointData)
WHERE (endpoint.hr_pfs_p_value IS NOT NULL AND endpoint.hr_pfs_p_value < $p_value_threshold)
   OR (endpoint.hr_os_p_value IS NOT NULL AND endpoint.hr_os_p_value < $p_value_threshold)

// 检查删失点密集度
WITH trial, endpoint, out
WHERE out.censoring_density_score IS NOT NULL 
  AND out.censoring_density_score > $censoring_threshold

// 获取关联的KM曲线资源
OPTIONAL MATCH (endpoint)-[:HAS_ASSET]->(asset:MediaAsset)
WHERE asset.asset_type = 'KM曲线'

// 获取里程碑数据
OPTIONAL MATCH (endpoint)-[:HAS_LANDMARK]->(landmark:LandmarkNode)

RETURN {
    trial: trial {.nct_id, .title, .phase, .enrollment_actual},
    endpoint: endpoint {
        .mpfs_months, .mos_months, .orr_percent,
        .hr_pfs, .hr_pfs_p_value,
        .hr_os, .hr_os_p_value,
        .grade3_plus_ae_rate
    },
    data_quality: {
        censoring_density: out.censoring_density_score,
        tail_effect: out.tail_effect_strength,
        reliability_flag: out.data_reliability_flag
    },
    km_asset: asset.url,
    landmarks: collect(landmark {
        .month_12_rate, .month_24_rate, .month_36_rate,
        .plateau_detected, .plateau_rate
    }),
    warning_level: CASE
        WHEN out.censoring_density_score > 0.7 
             AND (endpoint.hr_pfs_p_value < 0.001 OR endpoint.hr_os_p_value < 0.001)
        THEN 'HIGH_RISK'
        WHEN out.censoring_density_score > 0.5 
             AND (endpoint.hr_pfs_p_value < 0.01 OR endpoint.hr_os_p_value < 0.01)
        THEN 'MEDIUM_RISK'
        ELSE 'LOW_RISK'
    END
} as integrity_check

ORDER BY integrity_check.warning_level DESC
"""

SUSPICIOUS_DATA_QUERY = """
// 查找统计学结果与临床意义不匹配的数据
// 参数: 无

MATCH (trial:Trial)-[:OUTPUTS]->(endpoint:EndpointData)

// 查找p值极显著但HR接近1的情况（可能是样本量过大导致的假阳性）
WHERE (endpoint.hr_pfs_p_value < 0.01 AND endpoint.hr_pfs > 0.85)
   OR (endpoint.hr_os_p_value < 0.01 AND endpoint.hr_os > 0.85)
   OR (endpoint.orr_percent > 80 AND endpoint.grade3_plus_ae_rate > 60)

OPTIONAL MATCH (trial)-[:OUTPUTS]->()<-[:DEVELOPED_BY]-(company:Company)

RETURN {
    trial_nct: trial.nct_id,
    trial_phase: trial.phase,
    company: company.name,
    suspicious_metrics: {
        hr_pfs: endpoint.hr_pfs,
        hr_pfs_p: endpoint.hr_pfs_p_value,
        hr_os: endpoint.hr_os,
        hr_os_p: endpoint.hr_os_p_value,
        orr: endpoint.orr_percent,
        ae_rate: endpoint.grade3_plus_ae_rate
    },
    concern: CASE
        WHEN endpoint.hr_pfs > 0.85 AND endpoint.hr_pfs_p_value < 0.01
        THEN 'HR接近1但p值显著，需审查样本量和终点定义'
        WHEN endpoint.orr_percent > 80 AND endpoint.grade3_plus_ae_rate > 60
        THEN '高缓解率伴高毒性，需评估风险收益比'
        ELSE '其他异常'
    END
} as suspicious_finding
"""

# ==============================================================================
# 通用查询模板
# ==============================================================================

DRUG_FULL_PROFILE_QUERY = """
// 获取药物完整画像
// 参数: $drug_id - 药物ID

MATCH (drug:Drug {id: $drug_id})

// 公司信息
OPTIONAL MATCH (drug)-[:DEVELOPED_BY]->(company:Company)

// 适应症和治疗关系
OPTIONAL MATCH (drug)-[treats:TREATS]->(ind:Indication)

// 临床实验和终点数据
OPTIONAL MATCH (trial:Trial)-[:OUTPUTS]->(drug)
OPTIONAL MATCH (trial)-[:OUTPUTS]->(endpoint:EndpointData)

// 联合用药
OPTIONAL MATCH (drug)-[combo:COMBINED_WITH]-(partner:Drug)

// 外部因素
OPTIONAL MATCH (drug)-[:HAS_FACTOR]->(factor:ExternalFactor)

RETURN {
    drug: drug {.*},
    company: company {.name, .cash_balance, .pipeline_count},
    indications: collect(DISTINCT {
        indication: ind {.name, .prevalence, .unmet_need_score},
        treatment_line: treats.treatment_line,
        priority: treats.priority,
        approval_status: treats.approval_status
    }),
    trials: collect(DISTINCT {
        nct_id: trial.nct_id,
        phase: trial.phase,
        status: trial.status,
        endpoints: {
            mpfs: endpoint.mpfs_months,
            mos: endpoint.mos_months,
            orr: endpoint.orr_percent
        }
    }),
    combinations: collect(DISTINCT {
        partner: partner.name,
        synergy_score: combo.synergy_score
    }),
    external_factors: collect(DISTINCT factor {.*})
} as drug_profile
"""

INDICATION_LANDSCAPE_QUERY = """
// 获取适应症竞争格局
// 参数: $indication_id - 适应症ID

MATCH (ind:Indication {id: $indication_id})

// 当前标准疗法
OPTIONAL MATCH (ind)-[soc_rel:HAS_SOC]->(soc:Drug)
WHERE soc_rel.is_current_soc = true

// 所有治疗药物
OPTIONAL MATCH (drug:Drug)-[treats:TREATS]->(ind)
OPTIONAL MATCH (drug)-[:DEVELOPED_BY]->(company:Company)
OPTIONAL MATCH (drug)<-[:OUTPUTS]-(trial:Trial)
OPTIONAL MATCH (trial)-[:OUTPUTS]->(endpoint:EndpointData)

RETURN {
    indication: ind {.*},
    current_soc: soc {.name, .target, .moa},
    soc_benchmark: soc_rel.soc_efficacy_benchmark,
    
    competitive_landscape: collect(DISTINCT {
        drug: drug {.name, .molecule_type, .target},
        company: company.name,
        treatment_line: treats.treatment_line,
        development_stage: treats.development_stage,
        latest_trial: {
            nct_id: trial.nct_id,
            phase: trial.phase,
            status: trial.status
        },
        best_efficacy: {
            mpfs: max(endpoint.mpfs_months),
            mos: max(endpoint.mos_months),
            orr: max(endpoint.orr_percent)
        }
    }),
    
    summary: {
        total_drugs: count(DISTINCT drug),
        drugs_in_phase3: count(DISTINCT CASE WHEN trial.phase = 'Phase III' THEN drug END),
        drugs_approved: count(DISTINCT CASE WHEN treats.approval_status = '已获批' THEN drug END)
    }
} as landscape
"""

COMPANY_PIPELINE_QUERY = """
// 获取公司管线概览
// 参数: $company_id - 公司ID

MATCH (company:Company {id: $company_id})

// 药物管线
OPTIONAL MATCH (drug:Drug)-[:DEVELOPED_BY]->(company)
OPTIONAL MATCH (drug)-[treats:TREATS]->(ind:Indication)
OPTIONAL MATCH (drug)<-[:OUTPUTS]-(trial:Trial)

RETURN {
    company: company {.*},
    
    pipeline: collect(DISTINCT {
        drug: drug {.name, .molecule_type, .target, .moa},
        indications: collect(DISTINCT {
            name: ind.name,
            treatment_line: treats.treatment_line,
            stage: treats.development_stage
        }),
        trials: collect(DISTINCT {
            nct_id: trial.nct_id,
            phase: trial.phase,
            status: trial.status
        })
    }),
    
    pipeline_summary: {
        total_drugs: count(DISTINCT drug),
        by_phase: {
            preclinical: count(DISTINCT CASE WHEN trial.phase = '临床前' THEN drug END),
            phase1: count(DISTINCT CASE WHEN trial.phase IN ['Phase I', 'Phase I/II'] THEN drug END),
            phase2: count(DISTINCT CASE WHEN trial.phase IN ['Phase II', 'Phase II/III'] THEN drug END),
            phase3: count(DISTINCT CASE WHEN trial.phase = 'Phase III' THEN drug END),
            approved: count(DISTINCT CASE WHEN trial.phase = '已获批' THEN drug END)
        },
        by_molecule_type: collect(DISTINCT drug.molecule_type)
    }
} as company_pipeline
"""

