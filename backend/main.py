from app.logging_config import setup_logging
from app.routes import create_app

# Configure logging once for the whole process.
setup_logging()

# FastAPI application instance for uvicorn.
app = create_app()


def run() -> None:
    import uvicorn

    # Use our own logging configuration configured in app.logging_config.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_config=None)


if __name__ == "__main__":
    run()
