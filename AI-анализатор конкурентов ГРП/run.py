import uvicorn

from backend.config import settings
from backend.main import app


if __name__ == "__main__":
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)

