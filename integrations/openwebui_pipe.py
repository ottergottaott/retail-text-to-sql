"""
title: Retail Analyst
author: Retail assessment project
version: 0.2.0
description: Thin transport adapter to the authorized retail LangGraph backend.
requirements: httpx>=0.27.0
"""
import json
import re
from html import escape
from urllib.parse import quote, urlencode
from typing import Literal
import httpx
from pydantic import BaseModel, Field


def report_library(reports):
    """Authorized backend results; links prefill a new chat, never carry secrets."""
    lines = ["### Saved reports", "", "Select a report to open it in a new chat tab. If your WebUI version only fills the input, review and send the command.", ""]
    for report in reversed(reports):
        rid = str(report.get("id", ""))
        if not re.fullmatch(r"rep_[A-Za-z0-9]+", rid):
            continue
        title = escape(str(report.get("title") or "Untitled report")).replace("\n", " ")
        title = re.sub(r"([\\`*_[\]{}()!|])", r"\\\1", title)
        command = quote("Open saved report " + rid, safe="")
        lines.append(f"- [{title}](/?models=retail_assessment_pipe&q={command}) · `{rid}`")
    if len(lines) == 4:
        lines.append("You have no saved reports.")
    lines.extend(["", "Reports are stored independently of chat history. This list is a snapshot; ask for the list again to refresh it."])
    return "\n".join(lines)


class Pipe:
    class Valves(BaseModel):
        API_URL: str = Field(default="http://api:8000", description="Retail backend URL")
        ADAPTER_SECRET: str = Field(default="", description="Server-only backend adapter secret")
        REPORT_DISPLAY: Literal["both", "artifact", "embedded", "text"] = Field(default="both",
            description="Report presentation: Artifact panel, embedded card, both, or plain text")

    def __init__(self):
        self.valves = self.Valves()

    async def pipe(self, body: dict, __user__: dict = None, __chat_id__: str = None, __message_id__: str = None,
                   __event_emitter__=None, __task__: str = None):
        # Auxiliary title/tag jobs must not trigger analysis or report mutations.
        if __task__:
            return ""
        user = (__user__ or {}).get("id")
        if not user or not __chat_id__ or not self.valves.ADAPTER_SECRET:
            return "Retail integration is not configured: authenticated user, chat ID and adapter credentials are required."
        messages = [m for m in body.get("messages", []) if m.get("role") == "user"]
        content = messages[-1].get("content") if messages else None
        if not isinstance(content, str):
            return "Send a text question; attachments are not supported by this retail workflow."

        async def status(description, done=False):
            if __event_emitter__:
                try:
                    await __event_emitter__({"type": "status", "data": {"description": description, "done": done}})
                except Exception:
                    pass  # Status transport must not retry a committed backend operation.

        labels = {"context": "Loading analysis context", "model": "Planning analysis",
            "query": "Querying authorized retail data", "retrieval": "Finding analyst examples",
            "tool": "Running requested operation", "report_review": "Reviewing report against query evidence",
            "response": "Preparing response"}
        await status("Connecting to retail analyst")
        try:
            async with httpx.AsyncClient(timeout=150) as client:
                async with client.stream("POST", self.valves.API_URL.rstrip("/") + "/chat/stream",
                    headers={"Authorization": f"Bearer {self.valves.ADAPTER_SECRET}", "X-Webui-User": user},
                    json={"message": content, "external_chat_id": __chat_id__,
                          "external_message_id": __message_id__,
                          "include_report_view": self.valves.REPORT_DISPLAY != "text"}) as response:
                    if response.status_code != 200:
                        await status("Retail request rejected", True)
                        return "The retail backend rejected this request. Check your account mapping and access."
                    event_type, data = "", []
                    async for line in response.aiter_lines():
                        if line.startswith("event:"):
                            event_type = line[6:].strip()
                        elif line.startswith("data:"):
                            data.append(line[5:].lstrip())
                        elif not line and data:
                            event = json.loads("\n".join(data)); data = []
                            if event_type == "progress":
                                description = labels.get(event.get("stage"))
                                if description:
                                    await status(description)
                            elif event_type == "error":
                                await status("Retail request stopped", True)
                                return event.get("detail", "The request could not complete.")
                            elif event_type == "result":
                                answer = event["answer"]
                                if isinstance(event.get("management"), list) and self.valves.REPORT_DISPLAY != "text":
                                    answer = report_library(event["management"])
                                view = event.get("report_view")
                                if view and self.valves.REPORT_DISPLAY != "text":
                                    if __event_emitter__ and self.valves.REPORT_DISPLAY in {"both", "embedded"}:
                                        try:
                                            await __event_emitter__({"type": "embeds",
                                                "data": {"embeds": [view["preview_html"]]}})
                                        except Exception:
                                            pass  # UI failure cannot retry or invalidate a saved report.
                                    if self.valves.REPORT_DISPLAY in {"both", "artifact"}:
                                        # Keep the Artifact fence outside details: WebUI strips them
                                        # before discovering HTML artifacts. No model-generated HTML.
                                        rid = view.get("report_id")
                                        receipt = f'Saved report `{rid}`. You can reopen it from any chat.' if rid else \
                                            'This analysis is not saved yet. Ask me to save it to keep it in your report library.'
                                        # Full text remains in the accessible HTML and in the normal
                                        # API/CLI response. Avoid duplicating the entire report in chat.
                                        brief = '### Report ready\n\n' + receipt if view.get("title") else answer
                                        hint = 'Expand the card above to read it here, or open **Preview** below for the full report in Artifacts.' \
                                            if self.valves.REPORT_DISPLAY == "both" else \
                                            'Open **Preview** below for the full report in Artifacts.'
                                        answer = brief + '\n\n' + hint + '\n\n```html\n' + view["html"] + '\n```'
                                await status("Complete · " + event["mode"], True)
                                # Return final text/Artifact for persistence; embeds are supplementary.
                                links = []
                                if all(isinstance(v, str) and 0 < len(v) <= 200
                                       for v in (__chat_id__, __message_id__)):
                                    reference = urlencode({'chat': __chat_id__, 'message': __message_id__})
                                    links.append(f'[**Give feedback**](/static/retail-learning.html?{reference})')
                                links.append('[**My preferences**](/static/retail-learning.html#preferences)')
                                return answer + '\n\n---\n\n' + ' · '.join(links)
            await status("Connection ended before completion", True)
            return "No final response arrived. Check saved reports before retrying a save or deletion."
        except (httpx.HTTPError, ValueError, KeyError):
            await status("Retail service unavailable", True)
            return "The retail service is unavailable or its response was interrupted. Check saved reports before retrying a save or deletion."
