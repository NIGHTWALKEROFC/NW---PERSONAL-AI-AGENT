"""
dashboard/routers/contacts.py

The CONTACTS dashboard section from spec section 18, backed by
database/contact_store.py from Phase 4.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from database.contact_store import list_contacts, get_contact_memories
from database.memory_store import get_messages_for_contact


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/contacts", response_class=HTMLResponse)
    def contacts_page(request: Request):
        contacts = list_contacts()
        return templates.TemplateResponse(request, "contacts.html", {
            "contacts": contacts,
        })

    @router.get("/contacts/{contact_id}", response_class=HTMLResponse)
    def contact_detail(request: Request, contact_id: int):
        contacts = list_contacts()
        contact = next((c for c in contacts if c["id"] == contact_id), None)
        memories = get_contact_memories(contact_id)
        messages = get_messages_for_contact(contact_id)

        return templates.TemplateResponse(request, "contact_detail.html", {
            "contact": contact,
            "memories": memories,
            "messages": messages[-30:],
        })

    return router
