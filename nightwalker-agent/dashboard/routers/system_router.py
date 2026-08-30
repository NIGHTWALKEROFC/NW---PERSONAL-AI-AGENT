"""
dashboard/routers/system_router.py

The SYSTEM dashboard section from spec section 18 / section 22
(laptop optimization): CPU/RAM/disk usage and database file size.

GPU/VRAM monitoring is not included — psutil doesn't expose NVIDIA GPU
stats, and adding a GPU-specific library (e.g. pynvml) is a bigger
dependency than this page needs. If you want live GPU usage, Task
Manager's Performance tab already shows it.
"""

import os

import psutil
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from database.db import DB_PATH


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/system", response_class=HTMLResponse)
    def system_page(request: Request):
        cpu_percent = psutil.cpu_percent(interval=0.3)
        cpu_count = psutil.cpu_count()
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage(os.path.abspath(os.sep))

        db_size_mb = round(os.path.getsize(DB_PATH) / (1024**2), 2) if os.path.exists(DB_PATH) else 0

        return templates.TemplateResponse(request, "system.html", {
            "cpu_percent": cpu_percent,
            "cpu_count": cpu_count,
            "ram_percent": ram.percent,
            "ram_used_gb": round(ram.used / (1024**3), 1),
            "ram_total_gb": round(ram.total / (1024**3), 1),
            "disk_percent": disk.percent,
            "disk_used_gb": round(disk.used / (1024**3), 1),
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "db_size_mb": db_size_mb,
        })

    return router
