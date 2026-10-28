from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import Base, SessionLocal, engine, make_engine, make_sessionmaker
from app.errors import install_error_handlers
from app.reminders import start_reminder_loop, stop_reminder_loop
from app.routes import booking, connector, doctor, public, sync
from app.seed import seed
from app.utils import now_iso


def create_app(database_url: str | None = None, create_tables: bool = False) -> FastAPI:
    url = database_url or settings.database_url
    db_engine = engine if database_url is None else make_engine(url)
    session_factory = SessionLocal if database_url is None else make_sessionmaker(db_engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.create_tables:
            Base.metadata.create_all(app.state.engine)
        with app.state.sessionmaker() as session:
            seed(session)
        start_reminder_loop()
        yield
        await stop_reminder_loop()
        if database_url is not None:
            app.state.engine.dispose()

    app = FastAPI(
        title="Agenda Central",
        description=(
            "Agenda central multi-établissements LIKSOFT : espace médecin, synchro app "
            "local-first (LWW), réservation patient, connecteur SIH."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.engine = db_engine
    app.state.sessionmaker = session_factory
    app.state.create_tables = create_tables

    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["santé"])
    def health():
        return {"ok": True, "service": settings.service_name, "time": now_iso()}

    app.include_router(sync.router)
    app.include_router(doctor.router)
    app.include_router(booking.router)
    app.include_router(connector.router)
    app.include_router(public.router)

    async def route_404(_request: Request):
        return JSONResponse(status_code=404, content={"error": "Route inconnue"})

    app.add_api_route(
        "/{full_path:path}",
        route_404,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    return app


app = create_app()
