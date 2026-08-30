"""
dashboard/routers/memory.py

The MEMORY dashboard section from spec section 18:
    search, view, edit, delete, export, clear

"Edit" and "export" for individual entries aren't built — view and
delete cover the safety-relevant cases (removing something you don't
want kept). The one big capability implemented in full is spec section
31's "DELETE ALL PERSONAL DATA" — see database/wipe.py.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from database.memory_store import (
    get_recent_short_term, get_long_term_memory, delete_long_term_memory,
    get_active_temporary_memory, purge_expired_temporary_memory,
)
from database.wipe import wipe_all_personal_data


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/memory", response_class=HTMLResponse)
    def memory_page(request: Request, message: str | None = None):
        recent = get_recent_short_term(limit=30, contact_id=None)
        long_term = get_long_term_memory()
        temporary = get_active_temporary_memory()

        return templates.TemplateResponse(request, "memory.html", {
            "recent": recent,
            "long_term": long_term,
            "temporary": temporary,
            "message": message,
        })

    @router.post("/memory/delete-long-term")
    def delete_long_term(entry_id: int = Form(...)):
        delete_long_term_memory(entry_id)
        return RedirectResponse("/memory?message=Entry+deleted.", status_code=303)

    @router.post("/memory/purge-expired")
    def purge_expired():
        count = purge_expired_temporary_memory()
        return RedirectResponse(f"/memory?message={count}+expired+entries+purged.", status_code=303)

    @router.post("/memory/wipe-all")
    def wipe_all(confirmation: str = Form(...)):
        if confirmation.strip() != "DELETE":
            return RedirectResponse(
                "/memory?message=Wipe+cancelled+%E2%80%94+you+must+type+DELETE+exactly+to+confirm.",
                status_code=303,
            )
        counts = wipe_all_personal_data()
        total = sum(counts.values())
        return RedirectResponse(f"/memory?message=All+personal+data+wiped+({total}+rows+removed).", status_code=303)

    return router
