from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.routing import Mount, Route


def create_starlette_app(
    mcp_server: Server, *, debug: bool = False
) -> Starlette:
    """Create a Starlette application that can provide the mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        # The block below can be implemented for security. A bearer token can be validated to ensure user has proper
        # access to resources on a server
        # Check if the request has the Authorization header
        # if "Authorization" in request.headers:
        #     # Check if the Authorization header is valid
        #     if request.headers["Authorization"] != f"Bearer {api_key}":
        #         raise HTTPException(status_code=401, detail="Invalid API key")

        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )