"""
dashboard/routers/personality.py

The PERSONALITY dashboard section from spec section 18:
    show/edit english style, vocabulary, slang, emoji usage,
    punctuation, capitalization, message length, humor, formality,
    language mixing, confidence

Full editing of every trait isn't built here — the traits are
extracted from real evidence (onboarding, imports, corrections), so
free-editing them would let the displayed profile drift from the
actual evidence behind it. What IS editable here: boundaries
(never_say / actions_never_allowed / actions_requiring_approval),
since those are direct declarations, not inferred patterns, and
adding one is safe to do at any time.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from agent.personality.profile_store import load_profile, save_profile


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/personality", response_class=HTMLResponse)
    def personality_page(request: Request, message: str | None = None):
        profile = load_profile()
        return templates.TemplateResponse(request, "personality.html", {
            "profile": profile,
            "message": message,
        })

    @router.post("/personality/add-boundary")
    def add_boundary(boundary_type: str = Form(...), value: str = Form(...)):
        valid_types = {"never_say", "actions_never_allowed", "actions_requiring_approval"}
        if boundary_type not in valid_types or not value.strip():
            return RedirectResponse("/personality", status_code=303)

        profile = load_profile()
        if value.strip() not in profile["boundaries"][boundary_type]:
            profile["boundaries"][boundary_type].append(value.strip())
            save_profile(profile)

        return RedirectResponse("/personality?message=Boundary+added.", status_code=303)

    @router.post("/personality/remove-boundary")
    def remove_boundary(boundary_type: str = Form(...), value: str = Form(...)):
        profile = load_profile()
        if boundary_type in profile["boundaries"] and value in profile["boundaries"][boundary_type]:
            profile["boundaries"][boundary_type].remove(value)
            save_profile(profile)
        return RedirectResponse("/personality?message=Boundary+removed.", status_code=303)

    return router
