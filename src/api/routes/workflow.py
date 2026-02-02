# 工作流路由
"""
LangGraph 工作流 API
"""

from typing import Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json

from src.graph import run_workflow, run_workflow_stream
from src.utils import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ==================== 请求/响应模型 ====================

class WorkflowRequest(BaseModel):
    """工作流请求"""
    query: str
    session_id: str = "default"
    max_iterations: int = 10


class WorkflowResponse(BaseModel):
    """工作流响应"""
    session_id: str
    query: str
    final_report: str
    summary: str
    completed_tasks: list[dict[str, Any]] = Field(default_factory=list)
    analysis_results: list[dict[str, Any]] = Field(default_factory=list)
    extracted_entities_count: int = 0
    created_nodes_count: int = 0


class ExtractRequest(BaseModel):
    """数据提取请求"""
    text: str
    source: str = "manual"
    target_entities: list[str] = Field(
        default=["Drug", "Company", "Trial"],
        description="要提取的实体类型"
    )


class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    session_id: str = "default"


# ==================== 工作流 API ====================

@router.post("/run", response_model=WorkflowResponse)
async def run_workflow_api(request: WorkflowRequest):
    """运行完整工作流
    
    基于用户查询自动执行:
    1. 意图理解
    2. 任务分解
    3. 数据提取/图谱查询/分析
    4. 报告生成
    
    适用于复杂的分析任务。
    """
    try:
        final_state = await run_workflow(
            user_input=request.query,
            session_id=request.session_id,
            max_iterations=request.max_iterations,
        )
        
        if not final_state:
            raise HTTPException(status_code=500, detail="Workflow returned no state")
        
        return WorkflowResponse(
            session_id=request.session_id,
            query=request.query,
            final_report=final_state.get("final_report", ""),
            summary=final_state.get("summary", ""),
            completed_tasks=[
                t.model_dump() if hasattr(t, "model_dump") else t
                for t in final_state.get("completed_tasks", [])
            ],
            analysis_results=[
                r.model_dump() if hasattr(r, "model_dump") else r
                for r in final_state.get("analysis_results", [])
            ],
            extracted_entities_count=len(final_state.get("extracted_entities", [])),
            created_nodes_count=len(final_state.get("created_nodes", [])),
        )
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run/stream")
async def run_workflow_stream_api(request: WorkflowRequest):
    """流式运行工作流
    
    实时返回工作流执行状态，适用于需要实时反馈的场景。
    """
    async def generate():
        try:
            async for state in run_workflow_stream(
                user_input=request.query,
                session_id=request.session_id,
                max_iterations=request.max_iterations,
            ):
                # 提取最新消息
                messages = state.get("messages", [])
                if messages:
                    last_msg = messages[-1]
                    content = ""
                    if hasattr(last_msg, "content"):
                        content = last_msg.content
                    elif isinstance(last_msg, dict):
                        content = last_msg.get("content", "")
                    
                    if content:
                        yield f"data: {json.dumps({'message': content}, ensure_ascii=False)}\n\n"
                
                # 检查是否完成
                if not state.get("should_continue", True):
                    final_data = {
                        "type": "complete",
                        "final_report": state.get("final_report", ""),
                        "summary": state.get("summary", ""),
                    }
                    yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"
                    break
                    
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/extract")
async def extract_entities(request: ExtractRequest):
    """数据提取
    
    从文本中提取结构化实体数据。
    
    支持的实体类型:
    - Drug: 药物信息
    - Company: 公司信息
    - Indication: 适应症信息
    - Trial: 临床试验信息
    - EndpointData: 终点数据
    """
    # 构建提取任务的工作流
    query = f"""请从以下文本中提取 {', '.join(request.target_entities)} 类型的实体:

来源: {request.source}
文本内容:
{request.text[:5000]}
"""
    
    try:
        final_state = await run_workflow(
            user_input=query,
            session_id="extract_" + request.source,
            max_iterations=3,
        )
        
        extracted = final_state.get("extracted_entities", [])
        
        return {
            "source": request.source,
            "entities": [
                e.model_dump() if hasattr(e, "model_dump") else e
                for e in extracted
            ],
            "count": len(extracted),
        }
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def chat(request: ChatRequest):
    """简单对话
    
    基于知识图谱的问答对话。
    """
    try:
        final_state = await run_workflow(
            user_input=request.message,
            session_id=request.session_id,
            max_iterations=5,
        )
        
        # 提取最后的 AI 消息
        messages = final_state.get("messages", [])
        response = ""
        
        for msg in reversed(messages):
            if hasattr(msg, "content") and hasattr(msg, "type"):
                if msg.type == "ai":
                    response = msg.content
                    break
            elif isinstance(msg, dict) and msg.get("role") == "assistant":
                response = msg.get("content", "")
                break
        
        if not response:
            response = final_state.get("summary", "抱歉，我无法回答这个问题。")
        
        return {
            "session_id": request.session_id,
            "message": request.message,
            "response": response,
        }
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

