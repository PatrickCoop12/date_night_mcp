import asyncio
import json
import os
from typing import Optional
from contextlib import AsyncExitStack
import yaml
from mcp import ClientSession
from mcp.client.sse import sse_client
from google import genai
from google.genai import types

from dotenv import load_dotenv

load_dotenv("../.env")

class MCPClient:
    def __init__(self, name: str):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        self.messages = []
        self.name = name
        self.system_prompt = "You are a helpful assistant that can help with a users personal finances. You carefully explain any action you have taken."

    async def connect_to_sse_server(self, server_url: str):
        """Connect to an MCP server running with SSE transport"""
        self._streams_context = sse_client(url=server_url)
        streams = await self._streams_context.__aenter__()

        self._session_context = ClientSession(*streams)
        self.session: ClientSession = await self._session_context.__aenter__()

        await self.session.initialize()

        print("Initialized SSE client...")

    async def cleanup(self):
        """Properly clean up the session and streams"""
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:
            await self._streams_context.__aexit__(None, None, None)

    async def get_current_tool_names(self):
        response = await self.session.list_tools()
        available_tool_names = [tool.name for tool in response.tools]
        return available_tool_names

    async def chat_loop(self):
        while True:
            user_question = input("Enter a question: ")
            self.messages.append({
                "role": "user",
                "content": user_question
            })
            response = await self.session.list_tools()

            # for tool in response.tools:
            #     print(tool.name)
            #     print(tool.description)
            #     print(tool.inputSchema)

            available_tools = [
                types.Tool(
                    function_declarations=[
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": {
                                k: v
                                for k, v in tool.inputSchema.items()
                                if k not in ["additionalProperties", "$schema"]
                            },
                        }
                    ]
                ) for tool in response.tools]

            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=self.messages,
                config=types.GenerateContentConfig(
                    temperature=0,
                    tools=available_tools,
                    system_instruction=[self.system_prompt]
                ),
            )

            tool_results = []
            final_text = []

            if response.candidates[0].content.parts[0].function_call:
                function_call = response.candidates[0].content.parts[0].function_call

                tool_name = function_call.name
                tool_args = function_call.args

                result = await self.session.call_tool(tool_name, tool_args)
                tool_results.append({"call": tool_name, "result": result})
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                self.messages.append({
                    "role": "assistant",
                    "content": f"Calling tool {tool_name} with args {tool_args}, the reuslt is: " + "\n".join(
                        [x.text for x in result.content])
                })

                response = self.client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=self.messages,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        system_instruction=[self.system_prompt]
                    ),
                )

                print("FIRST RESPONSE", response)
                try:
                    final_text.append(response.text)
                    print(final_text[-1])
                except Exception as e:
                    print(e)

                    final_text.append(response.text)

                else:
                    final_text.append(response.text)



async def main(name, server_url):
    client = MCPClient(name=name)
    try:
        await client.connect_to_sse_server(server_url=server_url)
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    import sys

    asyncio.run(main(name=sys.argv[1], server_url=sys.argv[2]))