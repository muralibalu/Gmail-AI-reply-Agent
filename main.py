from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import init_db
from app.auth.router import router as auth_router
from app.drafts.router import router as drafts_router
from app.logger import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log every request: method, path, status code, response time."""
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        logger.info("-> %s %s", request.method, request.url.path)
        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            "<- %s %s | status: %d | %.1f ms",
            request.method, request.url.path, response.status_code, elapsed,
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== Draftly API starting up ===")
    init_db()
    logger.info("SQLite database initialised -- tables ready")
    yield
    logger.info("=== Draftly API shutting down ===")


app = FastAPI(
    title="Draftly - Gmail AI Reply Agent",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware order: last add_middleware = outermost = runs first.
# CORS must be outermost so preflight OPTIONS and error responses always
# get the Access-Control-Allow-Origin header.
app.add_middleware(LoggingMiddleware)   # inner  (runs second)
app.add_middleware(                     # outer  (runs first)
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(drafts_router)


@app.get("/")
def root():
    logger.debug("Health check endpoint called")
    return {"message": "Draftly API is running"}
