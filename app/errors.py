from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AgendaError(Exception):
    """Erreur métier → réponse JSON {"error": message} avec code HTTP."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AgendaError)
    async def _agenda_error(_request: Request, exc: AgendaError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"error": exc.message})

    @app.exception_handler(HTTPException)
    async def _http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        # Express répond 404 « Route inconnue » même pour une méthode non autorisée.
        if exc.status_code == 405:
            return JSONResponse(status_code=404, content={"error": "Route inconnue"})
        detail = exc.detail if isinstance(exc.detail, str) else "Erreur"
        return JSONResponse(status_code=exc.status_code, content={"error": detail})

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        for err in exc.errors():
            if err.get("type") == "json_invalid":
                return JSONResponse(status_code=400, content={"error": "JSON invalide"})
        return JSONResponse(status_code=400, content={"error": "Données invalides"})

    @app.exception_handler(Exception)
    async def _unexpected(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"error": "Erreur interne"})
