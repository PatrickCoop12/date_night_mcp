from mcp.server.fastmcp import FastMCP
from utils.starlette import create_starlette_app
import os
from dotenv import load_dotenv
from exa_py import Exa

load_dotenv("../.env")
mcp = FastMCP('general-research-server')

@mcp.tool()
def general_search_tool(query: str) -> str:
    """
    Helpful tool for general searches for items like events, information on locations, parking, etc.
    Args:
        query: Search query

    :return: Summarized search results
    """

    exa = Exa(os.getenv('EXA_API_KEY'))

    results = exa.search_and_contents(query, text=True)

    return results


if __name__ == "__main__":
    # mcp_server = mcp._mcp_server
    # import uvicorn
    # starlette_app = create_starlette_app(mcp_server, debug=True)
    # uvicorn.run(starlette_app, host="localhost", port=8030)
    mcp.run(transport='stdio')