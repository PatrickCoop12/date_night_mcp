from mcp.server.fastmcp import FastMCP
from utils.starlette import create_starlette_app
import os
from dotenv import load_dotenv
import requests

load_dotenv("../.env")
mcp = FastMCP('restuarant-research-server')

@mcp.tool()
def search_for_restuarants(location: str, categories: list) -> str:
    """
    Fetches restuarants data from Yelp API
    Args:
        location: the city yelp should be searching
        categories: the categories yelp should be searching

    :return: the restuarants data in json format
    """

    url = "https://api.yelp.com/v3/businesses/search"

    querystring = {"location": location, "categories": categories,
                   "sort_by": "best_match", "limit": "20"}

    payload = ""
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {os.getenv('YELP_API_KEY')}"
    }

    response = requests.request("GET", url, data=payload, headers=headers, params=querystring)

    return response.json()


if __name__ == "__main__":
    # mcp_server = mcp._mcp_server
    # import uvicorn
    # starlette_app = create_starlette_app(mcp_server, debug=True)
    # uvicorn.run(starlette_app, host="localhost", port=8010)
    mcp.run(transport='stdio')