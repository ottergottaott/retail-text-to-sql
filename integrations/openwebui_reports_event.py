"""
title: Retail Reports API
author: Retail assessment project
version: 0.1.0
description: Verified-user read-only proxy for the Retail Reports library.
requirements: httpx>=0.27.0
"""
import re
import httpx
from fastapi import Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from open_webui.utils.auth import get_verified_user


class Event:
    class Valves(BaseModel):
        API_URL: str = Field(default='http://api:8000', description='Retail backend URL')
        ADAPTER_SECRET: str = Field(default='', description='Server-only retail adapter secret')

    def __init__(self):
        self.valves = self.Valves()

    async def configuration(self, function_id):
        # Read current state per request: disable/valve edits take effect without restart.
        from open_webui.models.functions import Functions
        function = await Functions.get_function_by_id(function_id)
        if not function or not function.is_active:
            raise HTTPException(503, 'Report library is disabled.')
        return self.Valves(**(await Functions.get_function_valves_by_id(function_id) or {}))

    async def event(self, event: dict, __event_name__: str = None, __app__=None, __id__: str = None):
        about_me = (event.get('subject') or {}).get('id') == __id__
        if __app__ is None or not (__event_name__ == 'system.startup.completed' or
                (__event_name__ == 'function.enable_started' and about_me)):
            return
        prefix = '/api/retail-reports'
        if any(getattr(route, 'path', None) == prefix for route in __app__.routes):
            return

        async def fetch(path, user):
            config = await self.configuration(__id__)
            if not config.ADAPTER_SECRET:
                raise HTTPException(503, 'Report library is not configured.')
            try:
                async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                    response = await client.get(config.API_URL.rstrip('/') + path,
                        headers={'Authorization': 'Bearer ' + config.ADAPTER_SECRET,
                                 'X-Webui-User': user.id})
                if response.status_code != 200:
                    code = response.status_code if response.status_code in {401, 403, 404} else 503
                    raise HTTPException(code, 'Report not accessible.' if code in {401,403,404} else 'Report service unavailable.')
                return response
            except httpx.HTTPError:
                raise HTTPException(503, 'Report service unavailable.') from None

        async def reports(user=Depends(get_verified_user)):
            response = await fetch('/reports', user)
            try:
                data = response.json()
                if not isinstance(data, list):
                    raise ValueError()
                # Explicit metadata-only response; never forward diagnostics or credentials.
                records = [{'id': r['id'], 'title': r['title'], 'created': r['created']} for r in data]
            except (ValueError, KeyError, TypeError):
                raise HTTPException(503, 'Report service returned an invalid response.') from None
            return JSONResponse(records, headers={'Cache-Control': 'no-store'})

        async def report_html(report_id: str, user=Depends(get_verified_user)):
            if not re.fullmatch(r'rep_[A-Za-z0-9]+', report_id):
                raise HTTPException(404, 'Report not accessible.')
            response = await fetch('/reports/' + report_id + '/html', user)
            return HTMLResponse(response.text, headers={'Cache-Control': 'no-store',
                'X-Content-Type-Options': 'nosniff',
                'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"})

        # A mounted SPA catches all paths. Insert extension routes before it.
        previous = len(__app__.routes)
        __app__.add_api_route(prefix, reports, methods=['GET'])
        __app__.add_api_route(prefix + '/{report_id}/html', report_html, methods=['GET'])
        added = __app__.routes[previous:]
        del __app__.routes[previous:]
        position = next((i for i, route in enumerate(__app__.routes)
                         if getattr(route, 'path', None) == ''), len(__app__.routes))
        __app__.routes[position:position] = added
