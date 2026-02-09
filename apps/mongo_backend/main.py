"""
Main Application Entry Point - Server startup
"""

import uvicorn

from server import app


def main():
    """Start the application"""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable auto-reload for development
        log_level="info"
    )


if __name__ == "__main__":
    main()
