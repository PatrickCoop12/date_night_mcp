import yaml
from client import MCPClient
import os
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv("../.env")


class MultiClient:
    def __init__(self):
        self.clients = []
        self.system_prompt = "You are a helpful assistant that can help users to plan a date night. You carefully explain any action you have taken."
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        self.knowledge_gathered_so_far = ["You have access to these overall services: "]
        self.enum = []
        self.tools_discovered = [types.Tool(
                    function_declarations=[
                        {
                            "name": "service_tools",
                            "description": "Execute this tool with the name of a particular service to get the details description of the tools it contains",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "service_name": {
                                        "type": "string",
                                        "description": "name of the service.",
                                        "enum": self.enum
                                    },
                                },
                            },
                        },
                        ]
        )]


    async def cleanup(self):
        """Cleanup all clients"""
        for client in reversed(self.clients):
            await client.cleanup()

    async def service_tools(self, service_name: str) -> str:
        for client in self.clients:
            if client.name == service_name:
                response = await client.session.list_tools()
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
                self.tools_discovered.extend(available_tools)
                return available_tools

    async def load_servers(self, servers_file: str):
        """Load servers from a file"""
        with open(servers_file, "r") as f:
            servers = yaml.safe_load(f)

        print("THESE ARE ALL THE SERVERS", servers)

        for server in servers["servers"]:
            await self._add_server(server["name"], server["url"])
            # self.tools_discovered[0]['parameters']['properties']['service_name']['enum'].append(server['name'])
            #self.enum.append(server['name'])
            self.knowledge_gathered_so_far[0] += '\n'
            self.knowledge_gathered_so_far[0] += f"service_name: {server['name']}, description: {server['description']}"
            self.knowledge_gathered_so_far[0] += '\n'

    async def _add_server(self, name: str, server_url: str):  # should I add a name?
        """Add a client to the manager"""
        client = MCPClient(name=name)
        await client.connect_to_sse_server(server_url=server_url)
        self.clients.append(client)

    def has_tool_use(self, response):
        """Check if the response contains a tool use block."""
        if hasattr(response, 'content') and isinstance(response.content, list):
            for block in response.content:
                if hasattr(block, 'type') and block.type == 'tool_use':
                    return True
        return False

    async def chat_loop(self):
        while True:
            user_question = input("Enter a question: ")
            if user_question == 'quit': break
            chat_history = {}
            while True:
                messages = [
                    types.Content(
                        role="user",
                        parts=[types.Part(
                            text=f"""
                                We need to answer the user's query. There are various services available and each service has several tools, and these tools are what will help you answer the user's query.

                                Gather all the information you need about a particular service, the tools it offers, and even execute the tools to answer the query. 

                                You can call only one tool at a time to gather information.

                                You must make sure you call all the tools relevant to the user's query

                                Here's the information you have gathered so far:
                                {self.knowledge_gathered_so_far}

                                Once all information has been gathered and tasks have been executed, summarize the information and return the answer to the user's query.

                                ## User's query
                                {user_question}
                            """)]
                    ),]


                print("----------- Messages So Far ------------")
                # for message in messages:
                #     print(message["role"])
                #     print(message["content"])
                # print("-----------------------")


                response = self.client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=messages,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        tools=self.tools_discovered,
                        system_instruction=[self.system_prompt]
                    ),
                )

                current_knowledge = ""

                if response.candidates[0].content.parts[0].function_call:
                    function_call = response.candidates[0].content.parts[0].function_call
                    print(function_call.name)

                    tool_name = function_call.name
                    tool_args = function_call.args
                    if tool_name == "service_tools":
                        new_tools = await self.service_tools(tool_args["service_name"])
                        for tool in new_tools:
                            current_knowledge += f"The service {tool_args["service_name"]} has these tools: \n"
                            current_knowledge += f"Tool name: {tool.function_declarations[0].name}, Tool description: {tool.function_declarations[0].description}"
                    else:
                        for client in self.clients:
                            if tool_name in await client.get_current_tool_names():
                                result = await client.session.call_tool(tool_name, tool_args)
                                current_knowledge += '\n'
                                current_knowledge += f"The execution of the tool {tool.function_declarations[0].name}, provided the output: {result}"
                                current_knowledge += '\n'

                else:
                    print(response.text)
                    self.knowledge_gathered_so_far.append(response.text)
                    break

                self.knowledge_gathered_so_far.append(current_knowledge)


async def main():
    client = MultiClient()
    try:
        await client.load_servers(servers_file=os.getenv("SERVER_DETAILS"))  # change path
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    import sys

    asyncio.run(main())