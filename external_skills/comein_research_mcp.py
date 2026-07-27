# -*- coding: utf-8 -*-
"""
comein_research_mcp.py | 进门 MCP (comein-research) SSE 投研服务代理模块
"""
import asyncio
import json
import os
import sys

try:
    from mcp.client.sse import sse_client
    from mcp.client.session import ClientSession
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

COMEIN_MCP_SSE_URL = "https://mcp-server-global.comein.cn/mcp-servers/mcp-server-brm/sse"
COMEIN_MCP_KEY = "cm_749b197afeca4efb966e2b03dc6e5bcc"


async def _async_call_mcp_tool(tool_name: str, arguments: dict = None) -> dict:
    if not MCP_AVAILABLE:
        return {"status": "error", "message": "Python 'mcp' SDK未安装"}

    headers = {"x-mcp-key": COMEIN_MCP_KEY}
    arguments = arguments or {}

    try:
        async with sse_client(COMEIN_MCP_SSE_URL, headers=headers) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
                
                output_texts = []
                if hasattr(result, 'content') and result.content:
                    for item in result.content:
                        if hasattr(item, 'text'):
                            output_texts.append(item.text)
                        elif isinstance(item, str):
                            output_texts.append(item)
                
                return {
                    "status": "success",
                    "tool": tool_name,
                    "result": output_texts,
                    "raw_content": str(result)
                }
    except Exception as e:
        return {
            "status": "error",
            "tool": tool_name,
            "error_type": type(e).__name__,
            "message": str(e)
        }


async def _async_list_mcp_tools() -> dict:
    if not MCP_AVAILABLE:
        return {"status": "error", "message": "Python 'mcp' SDK未安装"}

    headers = {"x-mcp-key": COMEIN_MCP_KEY}
    try:
        async with sse_client(COMEIN_MCP_SSE_URL, headers=headers) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_res = await session.list_tools()
                
                tools_list = []
                for tool in tools_res.tools:
                    tools_list.append({
                        "name": tool.name,
                        "description": tool.description,
                        "schema": getattr(tool, 'inputSchema', {})
                    })
                return {
                    "status": "success",
                    "count": len(tools_list),
                    "tools": tools_list
                }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e)
        }


def comein_research_mcp(action: str = "list_tools", tool_name: str = "", arguments: dict = None, **kwargs) -> str:
    """
    进门 MCP(comein-research) 投研服务主调接口。
    :param action: "list_tools" 或 "call_tool"
    :param tool_name: 调用的进门 MCP 工具名称 (例如 "get_financial_snapshot", "company_report_date_search", "screen_funds")
    :param arguments: 工具所需的参数字典
    """
    if arguments is None and kwargs:
        arguments = kwargs

    loop = None
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if action == "list_tools":
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                res = pool.submit(lambda: asyncio.run(_async_list_mcp_tools())).result()
        else:
            res = loop.run_until_complete(_async_list_mcp_tools())
        return json.dumps(res, ensure_ascii=False, indent=2)

    elif action == "call_tool":
        if not tool_name:
            return json.dumps({"status": "error", "message": "未指定 tool_name"}, ensure_ascii=False)
        
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                res = pool.submit(lambda: asyncio.run(_async_call_mcp_tool(tool_name, arguments))).result()
        else:
            res = loop.run_until_complete(_async_call_mcp_tool(tool_name, arguments))
        return json.dumps(res, ensure_ascii=False, indent=2)

    else:
        return json.dumps({"status": "error", "message": f"不支持的 action: {action}"}, ensure_ascii=False)


if __name__ == '__main__':
    print("Testing comein_research_mcp list_tools ...")
    res_str = comein_research_mcp("list_tools")
    print(res_str[:500])
