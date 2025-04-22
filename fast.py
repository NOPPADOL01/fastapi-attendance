from fastapi import FastAPI, Request, Response
import httpx
import logging
from datetime import datetime
import uvicorn

app = FastAPI()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('traffic.log'),
        logging.StreamHandler()
    ]
)

# Target server configuration
TARGET_SERVER = "http://localhost:80"  # เปลี่ยนให้เป็น URL ของเซิร์ฟเวอร์ที่คุณต้องการ forward

@app.middleware("http")
async def proxy_and_log_traffic(request: Request, call_next):
    client_host = request.client.host if request.client else "unknown"
    
    # Log incoming request details
    logging.info(f"Incoming request: {request.method} {request.url} from {client_host}")
    logging.info(f"Headers: {dict(request.headers)}")

    try:
        # Prepare target URL
        target_url = f"{TARGET_SERVER}{request.url.path}"
        if request.url.query:
            target_url += f"?{request.url.query}"
        
        headers = dict(request.headers)
        headers.pop('host', None)  # Remove 'host' header since we're forwarding
        headers.pop('content-length', None)  # Remove 'content-length' header as well
        
        # Get the body of the request
        body = await request.body()

        # Forward the request to the target server using httpx
        async with httpx.AsyncClient() as client:
            proxy_response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body if body else None,
                timeout=30.0  # Timeout after 30 seconds
            )
        
        # Log response details
        logging.info(f"Forwarded to {target_url} - Status: {proxy_response.status_code}")
        logging.info(f"Response headers: {dict(proxy_response.headers)}")

        # Return the response back to the client
        return Response(
            content=proxy_response.content,
            status_code=proxy_response.status_code,
            headers=dict(proxy_response.headers),
            media_type=proxy_response.headers.get("content-type", None)
        )

    except httpx.ConnectError:
        logging.error(f"Failed to connect to target server at {TARGET_SERVER}")
        return Response(status_code=502, content="Bad Gateway")
    except Exception as e:
        logging.error(f"Error forwarding request: {str(e)}")
        return Response(status_code=500, content="Internal Server Error")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
