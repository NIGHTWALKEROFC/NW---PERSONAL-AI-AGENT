"""
dashboard/routers/platforms_router.py

The PLATFORMS dashboard section from spec section 18 — previously
always shown as "not built yet" in the nav. As of Phase 10, this is
real for one platform: Telegram, via the official Bot API. Adding a
second platform later means writing a new adapter (connectors/) and
this page will show it automatically via connectors.registry.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from connectors.registry import list_platforms, get_adapter
from database.contact_store import list_contacts


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/platforms", response_class=HTMLResponse)
    def platforms_page(request: Request):
        platform_status = []
        for name in list_platforms():
            adapter = get_adapter(name)
            linked_contacts = [c for c in list_contacts() if c.get("platform") == name]
            platform_status.append({
                "name": name,
                "configured": adapter.is_configured() if adapter else False,
                "linked_contacts": len(linked_contacts),
            })

        return templates.TemplateResponse(request, "platforms.html", {
            "platforms": platform_status,
        })

    return router
