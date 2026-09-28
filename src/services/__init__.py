"""GP services.

Each service is a package with the same shape: ``models.py`` is the contract,
``service.py`` the pure logic, ``client.py`` the protocol plus one implementation
per mode, and ``router.py`` the HTTP surface. FX is the exception — the service
itself runs in FM, so GP has a client and a thin route only.

``all_routers()`` imports inside the function so that importing this package never
drags in FastAPI or the registry, which keeps unit tests on a single service light.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import APIRouter


def all_routers() -> list[APIRouter]:
    """Every service router, in the order they are mounted on the app."""
    from src.services.budget.router import router as budget_router
    from src.services.config.router import router as config_router
    from src.services.fx.router import router as fx_router
    from src.services.need_calculator.router import router as need_calculator_router
    from src.services.need_profiler.router import router as need_profiler_router
    from src.services.people_like_you.router import router as people_like_you_router
    from src.services.plan.router import router as plan_router
    from src.services.premium.router import router as premium_router
    from src.services.social_security.router import router as social_security_router

    return [
        config_router,
        fx_router,
        social_security_router,
        people_like_you_router,
        need_profiler_router,
        need_calculator_router,
        premium_router,
        plan_router,
        budget_router,
    ]
