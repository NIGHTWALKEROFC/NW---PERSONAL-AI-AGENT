"""
dashboard/routers/model_router.py

The MODEL dashboard section from spec section 18, wired to
agent/brain/model_manager.py (Phase 1). Switching the model here does
NOT verify it's been pulled via `ollama pull` — that check happens the
next time something actually tries to use it (same as the CLI scripts).
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from agent.brain.model_client import ModelClient
from agent.brain.model_manager import get_active_model, list_candidates, set_active_model


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/model", response_class=HTMLResponse)
    def model_page(request: Request, message: str | None = None):
        active = get_active_model()
        candidates = list_candidates()
        client = ModelClient(active)
        ollama_up = client.is_available()

        return templates.TemplateResponse(request, "model.html", {
            "active": active,
            "candidates": candidates,
            "ollama_up": ollama_up,
            "message": message,
        })

    @router.post("/model/set-active")
    def set_active(model_name: str = Form(...)):
        set_active_model(model_name.strip())
        return RedirectResponse(f"/model?message=Active+model+set+to+{model_name.strip()}.", status_code=303)

    return router
