"""
FastAPI Server - Route definitions and API endpoints
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
# Register route modules
from routes.user import router as user_router, supplier_router
from routes.product import router as product_router
from routes.order import router as order_router
from routes.post import router as post_router
from db.mongo_db import init_db
from http import HTTPStatus
from shared.errors import AppError, ValueErrorMapper, ErrorCode


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    await init_db()
    print("Application started successfully")
    yield
    print("Application shutdown complete")


app = FastAPI(
    title="Social Commerce Platform API",
    description="API for social commerce with communities, posts, promotions, and products",
    version="1.0.0",
    lifespan=lifespan
)


# ----------------------------------------------------------------
# Global exception handlers
# ----------------------------------------------------------------

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                **({"details": exc.details} if exc.details else {}),
            }
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    mapped = ValueErrorMapper.map(exc)
    return JSONResponse(
        status_code=mapped.status_code,
        content={
            "error": {
                "code": mapped.error_code,
                "message": mapped.message,
                **({"details": mapped.details} if mapped.details else {}),
            }
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": ErrorCode.INTERNAL_ERROR,
                "message": "An unexpected error occurred",
            }
        },
    )


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "Social Commerce Platform API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": "connected"
    }




app.include_router(user_router)
app.include_router(supplier_router)
app.include_router(product_router)
app.include_router(order_router)
app.include_router(post_router)
