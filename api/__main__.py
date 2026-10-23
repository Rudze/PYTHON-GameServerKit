"""python -m api : starts the HTTP API (uvicorn) on API_HOST:API_PORT."""
import uvicorn

from common.config import settings

if __name__ == "__main__":
    uvicorn.run("api.app:app", host=settings().api_host, port=settings().api_port, proxy_headers=True)
