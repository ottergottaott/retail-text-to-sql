"""
title: Give feedback
author: Retail assessment project
version: 0.1.0
description: Review a specific response and submit feedback for analyst review.
"""
import json
from urllib.parse import urlencode


class Action:
    async def action(self, body: dict, __user__: dict = None, __event_call__=None,
                     __event_emitter__=None):
        if not (__user__ or {}).get('id'):
            return None
        chat,message=body.get('chat_id'),body.get('id')
        if not all(isinstance(v,str) and 0 < len(v) <= 200 for v in (chat,message)):
            return None
        url='/static/retail-learning.html?' + urlencode({'chat':chat,'message':message})
        if __event_call__:
            await __event_call__({'type':'execute','data':{'code':'window.location.assign('+json.dumps(url)+');'}})
        return None
