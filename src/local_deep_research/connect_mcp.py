from typing import Any
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from .config import mcp_url

MCP_SERVICE_URL = mcp_url 
tool_packages = [
    "chembl_mcp",
    "kegg_mcp",
    "string_mcp",
    "search_mcp",
    "pubchem_mcp",
    "ncbi_mcp",
    "uniprot_mcp",
    "tcga_mcp",
    "ensembl_mcp",
    "ucsc_mcp",
    "fda_drug_mcp",
    "opentargets_mcp",
    "monarch_mcp",
    "clinicaltrials_mcp",
    "pdb_mcp",
    "dbsearch_mcp",
]


mcp_servers = {
    package: {
        "transport": "streamable_http",
        "url": f"{MCP_SERVICE_URL}/mcp_index/{package}/mcp/",
    }
    for package in tool_packages
}


class OrigeneMCPToolClient:
    def __init__(self, mcp_servers: dict[str, Any], specified_tools: list = None):
        self.mcp_servers = mcp_servers
        self.mcp_tools = None
        self.mcp_tool_map = {}
        self.available_tools = specified_tools

    async def initialize(self):
        """Initialize async components"""
        client = MultiServerMCPClient(self.mcp_servers)

        self.tool2source = {}
        for pkg_name in self.mcp_servers.keys():
            async with client.session(pkg_name) as session:
                tools = await load_mcp_tools(session)
                self.tool2source.update(
                    {tool.name: pkg_name.replace("_mcp", "") for tool in tools}
                )

        self.mcp_tools = await client.get_tools()
        if self.available_tools:
            self.mcp_tools = [
                tool for tool in self.mcp_tools if tool.name in self.available_tools
            ]
        self.mcp_tool_map = {tool.name: tool for tool in self.mcp_tools}
        print(f"MCP server connected! Found {len(self.mcp_tools)} tools")
