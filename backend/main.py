import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import settings
from models.schemas import (
    ChatRequest,
    ChatResponse,
    ModelInfo,
    ModelListResponse,
    ModelSelectRequest,
    Prompt,
    PromptCreate,
    PromptListResponse,
    PromptUpdate,
    UploadResponse,
)
from services.llm import ollama
from services.file_parser import file_parser
from services.prompt_manager import prompt_manager
from services.chart_service import chart_service
from agents.sales_agent import sales_agent

app = FastAPI(title="AI Sales Analytics", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ---

@app.get("/api/models", response_model=ModelListResponse)
async def list_models():
    models = await ollama.list_models()
    return ModelListResponse(
        models=[
            ModelInfo(
                name=m.get("name", ""),
                size=m.get("size", 0),
                modified_at=m.get("modified_at"),
            )
            for m in models
        ]
    )


@app.put("/api/models/select")
async def select_model(req: ModelSelectRequest):
    return {"model": req.model, "status": "ok"}


# --- Upload ---

@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "Имя файла отсутствует")
    content = await file.read()
    try:
        df = file_parser.parse(file.filename, content)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Ошибка парсинга: {e}")

    session_id = str(uuid.uuid4())[:8]
    sales_agent.register_dataframe(session_id, df)
    file_info = file_parser.get_file_info(file.filename, df)
    return UploadResponse(session_id=session_id, file_info=file_info)


# --- Chat ---

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())[:8]
    result = await sales_agent.chat(
        user_message=req.message,
        session_id=session_id,
        model=req.model,
        system_prompt=req.system_prompt,
    )
    return ChatResponse(
        reply=result["reply"],
        chart_path=result.get("chart_path"),
        model_used=result["model_used"],
    )


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())[:8]

    async def generate():
        from services.prompt_manager import prompt_manager as pm

        system = req.system_prompt or pm.get_system_prompt()
        df = sales_agent.get_dataframe(session_id)
        if df is not None:
            df_info = sales_agent._get_data_info(df)
            system += f"\n\nТекущие данные:\n{df_info}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": req.message},
        ]

        model = req.model or settings.default_model
        stream = await ollama.chat(messages, model=model, stream=True)

        full_text = ""
        async for chunk in stream:
            full_text += chunk
            yield f"data: {chunk}\n\n"

        sales_agent.sessions[session_id] = df
        yield f"data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# --- Prompts ---

@app.get("/api/prompts", response_model=PromptListResponse)
async def list_prompts():
    return PromptListResponse(prompts=prompt_manager.list_prompts())


@app.get("/api/prompts/system")
async def get_system_prompt():
    return {"content": prompt_manager.get_system_prompt()}


@app.put("/api/prompts/system")
async def update_system_prompt(body: dict):
    content = body.get("content", "")
    prompt_manager.save_system_prompt(content)
    return {"status": "ok"}


@app.post("/api/prompts", response_model=Prompt)
async def create_prompt(req: PromptCreate):
    try:
        return prompt_manager.create_prompt(req)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.put("/api/prompts/{prompt_id}", response_model=Prompt)
async def update_prompt(prompt_id: str, req: PromptUpdate):
    result = prompt_manager.update_prompt(prompt_id, req)
    if not result:
        raise HTTPException(404, "Промпт не найден")
    return result


@app.delete("/api/prompts/{prompt_id}")
async def delete_prompt(prompt_id: str):
    if not prompt_manager.delete_prompt(prompt_id):
        raise HTTPException(404, "Промпт не найден")
    return {"status": "ok"}


@app.get("/api/prompts/templates/{key}")
async def get_template(key: str):
    content = prompt_manager.get_template(key)
    if not content:
        raise HTTPException(404, "Шаблон не найден")
    return {"content": content}


# --- Charts ---

@app.get("/api/charts")
async def list_charts():
    return {"charts": chart_service.list_charts()}


@app.get("/api/charts/{chart_id}")
async def get_chart(chart_id: str):
    html = chart_service.get_html(chart_id)
    if not html:
        raise HTTPException(404, "График не найден")
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


@app.delete("/api/charts/{chart_id}")
async def delete_chart(chart_id: str):
    if not chart_service.delete_chart(chart_id):
        raise HTTPException(404, "График не найден")
    return {"status": "ok"}


# --- Health ---

@app.get("/api/health")
async def health():
    try:
        models = await ollama.list_models()
        ollama_ok = True
    except Exception:
        ollama_ok = False
    return {
        "status": "ok",
        "ollama_connected": ollama_ok,
        "default_model": settings.default_model,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
