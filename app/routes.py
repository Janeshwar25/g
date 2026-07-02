from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
import pandas as pd
import io
import logging
# from archive.project_plan_agent import run_plan_builder, handle_updates
from engine.mapping import build_plan, get_optics_financials
from upload.update_smartsheet import update
from pydantic import BaseModel
from typing import List, Optional
import json

logger = logging.getLogger(__name__)

app = FastAPI()


@app.on_event("startup")
async def _startup_index_enterprise_kb() -> None:
    """Ensure the enterprise knowledge_base is indexed into the vector store."""
    try:
        from agent.knowledge_base_indexer import ensure_knowledge_base_index

        result = ensure_knowledge_base_index()
        logger.info(
            "[KB] startup indexing complete: indexed_files=%s indexed_chunks=%s skipped_files=%s",
            result.indexed_files,
            result.indexed_chunks,
            result.skipped_files,
        )
    except Exception:
        # Never block API startup
        logger.exception("[KB] startup indexing failed")

# pydantic

class ChatRequest(BaseModel):
     request: str

@app.post('/example')
async def chat2(request:ChatRequest):
     pass
     

@app.post("/chat")
async def chat(request: Request):
    # try:
        data = await request.json()
        # print("DATA", data)
        user_input = data.get("user_input", "")
        plan_params = data.get("plan_params", {})

        if user_input == "Update Request":
            st = data.get('st', '')
            update_options = data.get('update_options', {})

            # with open('plan_metadata.json', 'r') as file:
            #     data = json.load(file)
                
            # prj = data[st]['prj']
            
            # add prj to the function
            # update_from_rally(st, prj)
            
            update(st, update_options=update_options)
            return {"detail": "Updates processed successfully"}

        # Run the plan builder with the provided parameters
        plan_df = build_plan(plan_params)

        if plan_df is None or plan_df.empty:
            # logger.error("Failed to generate plan: Empty DataFrame")
            raise HTTPException(status_code=400, detail="Failed to generate plan")

        # Convert DataFrame to CSV string in memory (not saved to disk)
        csv_buffer = io.StringIO()
        plan_df.to_csv(csv_buffer, index=False)
        csv_string = csv_buffer.getvalue()
        
        # Return CSV as text
        return {"csv": csv_string}
    # except Exception as e:
    #     logger.error("Error in chat endpoint: %s", e)
    #     print(plan_params)
    #     raise HTTPException(status_code=500, detail="Internal Server Error")

class FinancialRequest(BaseModel):
    prj: str
    strategic_theme: str

@app.post("/financials")
async def generate_financials(request: FinancialRequest):
    try:
        # Call your function to get the DataFrame
        df = get_optics_financials(request.prj, request.strategic_theme)

        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="No financial data found for given inputs")

        # Convert DataFrame to JSON for frontend display
        return {"data": df.to_dict(orient="records")}
    except Exception as e:
        logging.error(f"Error generating financials: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


class LLMRequest(BaseModel):
    query: str
    chat_history: Optional[List[dict]] = []
    portfolio_filter: Optional[str] = "all"
    session_id: Optional[str] = None


@app.post("/llm")
async def help_bot_llm(request: LLMRequest):
    """
    AI Help Bot endpoint - answers questions using RAG context and the enterprise LLM gateway.
    """
    try:
        from agent.chatbot import HelpChatbot

        query = (request.query or "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query is required.")

        portfolio_filter = request.portfolio_filter or "all"
        chat_history = request.chat_history or []
        session_id = request.session_id

        bot = HelpChatbot()
        result = bot.answer(
            query=query,
            chat_history=chat_history,
            portfolio_filter=portfolio_filter,
            session_id=session_id,
        )

        return {
            "response": result.get("response", ""),
            "sources_used": result.get("sources_used", []),
            "mode": result.get("mode", "enterprise"),
        }
    except ValueError as e:
        logger.warning("Help bot bad request: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        # 🔴 HARD FAIL - No fallback in enterprise-only mode
        logger.exception("🔴 ENTERPRISE LLM GATEWAY FAILED - NO FALLBACK AVAILABLE")
        error_msg = (
            "Enterprise LLM Gateway failed. No fallback providers available. "
            "This is strict enterprise-only inference mode. "
            "Please verify gateway connectivity and credentials, then contact IT/DevOps."
        )
        raise HTTPException(
            status_code=503,
            detail=error_msg,
        )

@app.get("/api/retriever/stats")
async def get_retriever_stats():
    """
    Lightweight debug endpoint returning retrieval statistics.
    """
    try:
        from config import Config
        cfg = Config()
        if cfg.RETRIEVER_TYPE == "bm25":
            from agent.bm25_retriever import BM25Retriever
            retriever = BM25Retriever(cfg)
            return retriever.get_stats()
        else:
            return {"error": f"Stats not available for retriever type: {cfg.RETRIEVER_TYPE}"}
    except Exception as e:
        logger.error("Error fetching retriever stats: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch retriever stats")

if __name__ == '__main__':
    import uvicorn
    from config import Config
    config = Config()
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
