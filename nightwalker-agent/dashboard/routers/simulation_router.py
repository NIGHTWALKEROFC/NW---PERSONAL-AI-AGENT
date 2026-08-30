"""
dashboard/routers/simulation_router.py

Dashboard front-end for agent/simulation/simulator.py — spec section
32's simulation mode. Runs the full decision chain as a dry run with
no real approval created and no memory writes, showing the full
stage-by-stage trace.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse

from agent.simulation.simulator import simulate_incoming_message
from agent.brain.model_client import ModelClient
from agent.brain.model_manager import get_active_model


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/simulation", response_class=HTMLResponse)
    def simulation_page(request: Request):
        return templates.TemplateResponse(request, "simulation.html", {
            "result": None,
            "incoming_message": "",
            "contact_name": "",
        })

    @router.post("/simulation/run", response_class=HTMLResponse)
    def run_simulation(request: Request, incoming_message: str = Form(...), contact_name: str = Form("")):
        client = ModelClient(get_active_model())
        if not client.is_available():
            return templates.TemplateResponse(request, "simulation.html", {
                "result": None,
                "error": "Cannot reach Ollama. Make sure it's running.",
                "incoming_message": incoming_message,
                "contact_name": contact_name,
            })

        result = simulate_incoming_message(incoming_message, contact_name=contact_name or None)
        return templates.TemplateResponse(request, "simulation.html", {
            "result": result,
            "incoming_message": incoming_message,
            "contact_name": contact_name,
        })

    return router
