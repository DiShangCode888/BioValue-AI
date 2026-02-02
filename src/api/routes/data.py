# 数据摄入路由
"""
数据摄入 API
"""

from typing import Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from src.ingestion import WebCrawler, DocumentParser, ClinicalTrialsAPI
from src.utils import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ==================== 请求/响应模型 ====================

class CrawlRequest(BaseModel):
    """爬取请求"""
    url: str
    extract_links: bool = False
    max_pages: int = 1


class CrawlResponse(BaseModel):
    """爬取响应"""
    url: str
    status_code: int
    title: str
    text: str
    links: list[str] = Field(default_factory=list)
    error: str | None = None


class ParseResponse(BaseModel):
    """解析响应"""
    filename: str
    file_type: str
    text: str
    pages: int
    metadata: dict[str, Any]
    error: str | None = None


class TrialSearchRequest(BaseModel):
    """临床试验搜索请求"""
    query: str | None = None
    condition: str | None = None
    intervention: str | None = None
    sponsor: str | None = None
    status: list[str] | None = None
    phase: list[str] | None = None
    page_size: int = 20


class TrialResponse(BaseModel):
    """临床试验响应"""
    nct_id: str
    title: str
    status: str
    phase: str | None = None
    enrollment: int | None = None
    conditions: list[str] = Field(default_factory=list)


# ==================== 爬虫 API ====================

@router.post("/crawl", response_model=CrawlResponse)
async def crawl_url(request: CrawlRequest):
    """爬取网页内容"""
    crawler = WebCrawler()
    
    try:
        result = await crawler.fetch(request.url)
        
        return CrawlResponse(
            url=result.url,
            status_code=result.status_code,
            title=result.title,
            text=result.text[:10000],  # 限制返回长度
            links=result.links[:20] if request.extract_links else [],
            error=result.error,
        )
    except Exception as e:
        logger.error(f"Crawl failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await crawler.close()


@router.post("/crawl/site", response_model=list[CrawlResponse])
async def crawl_site(request: CrawlRequest):
    """爬取整个站点"""
    crawler = WebCrawler()
    
    try:
        results = await crawler.crawl_site(
            request.url,
            max_pages=min(request.max_pages, 10),  # 限制最大页面数
        )
        
        return [
            CrawlResponse(
                url=r.url,
                status_code=r.status_code,
                title=r.title,
                text=r.text[:5000],
                links=[],
                error=r.error,
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Site crawl failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await crawler.close()


# ==================== 文档解析 API ====================

@router.post("/parse/document", response_model=ParseResponse)
async def parse_document(
    file: UploadFile = File(...),
):
    """解析上传的文档
    
    支持格式: PDF, DOCX, TXT
    """
    parser = DocumentParser()
    
    # 检查文件类型
    filename = file.filename or "unknown"
    suffix = "." + filename.split(".")[-1].lower() if "." in filename else ""
    
    if suffix not in parser.supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Supported: {parser.supported_formats}"
        )
    
    try:
        # 保存临时文件
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # 解析文档
        result = parser.parse(tmp_path)
        
        # 删除临时文件
        os.unlink(tmp_path)
        
        if result.error:
            raise HTTPException(status_code=400, detail=result.error)
        
        return ParseResponse(
            filename=filename,
            file_type=result.file_type,
            text=result.text[:50000],  # 限制返回长度
            pages=result.pages,
            metadata=result.metadata,
            error=result.error,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Parse failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ClinicalTrials.gov API ====================

@router.post("/clinical-trials/search", response_model=list[TrialResponse])
async def search_clinical_trials(request: TrialSearchRequest):
    """搜索 ClinicalTrials.gov"""
    api = ClinicalTrialsAPI()
    
    try:
        results = await api.search_studies(
            query=request.query,
            condition=request.condition,
            intervention=request.intervention,
            sponsor=request.sponsor,
            status=request.status,
            phase=request.phase,
            page_size=request.page_size,
        )
        
        trials = []
        for study_data in results.get("studies", []):
            protocol = study_data.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})
            status_module = protocol.get("statusModule", {})
            design_module = protocol.get("designModule", {})
            conditions_module = protocol.get("conditionsModule", {})
            
            trials.append(TrialResponse(
                nct_id=id_module.get("nctId", ""),
                title=id_module.get("briefTitle", ""),
                status=status_module.get("overallStatus", ""),
                phase=design_module.get("phases", [None])[0] if design_module.get("phases") else None,
                enrollment=design_module.get("enrollmentInfo", {}).get("count"),
                conditions=conditions_module.get("conditions", []),
            ))
        
        return trials
    except Exception as e:
        logger.error(f"Clinical trials search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api.close()


@router.get("/clinical-trials/{nct_id}", response_model=TrialResponse)
async def get_clinical_trial(nct_id: str):
    """获取临床试验详情"""
    api = ClinicalTrialsAPI()
    
    try:
        study = await api.get_study(nct_id)
        
        if not study:
            raise HTTPException(status_code=404, detail="Trial not found")
        
        return TrialResponse(
            nct_id=study.nct_id,
            title=study.title,
            status=study.status,
            phase=study.phase,
            enrollment=study.enrollment,
            conditions=study.conditions,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get trial failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api.close()


@router.post("/clinical-trials/import/{nct_id}")
async def import_clinical_trial(nct_id: str):
    """导入临床试验到知识图谱"""
    from src.knowledge import get_neo4j_client
    
    api = ClinicalTrialsAPI()
    client = get_neo4j_client()
    
    try:
        # 获取试验数据
        study = await api.get_study(nct_id)
        if not study:
            raise HTTPException(status_code=404, detail="Trial not found")
        
        # 转换为节点
        trial_node = api.convert_to_trial_node(study)
        
        # 写入图谱
        await client.connect()
        node_id = await client.create_node(trial_node)
        
        return {
            "message": "Trial imported successfully",
            "nct_id": nct_id,
            "node_id": node_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import trial failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api.close()

