"""
title: My preferences
author: Retail assessment project
version: 0.1.0
description: Explicit presentation preferences saved across conversations.
"""


class Action:
    async def action(self, body: dict, __user__: dict = None, __event_call__=None):
        if (__user__ or {}).get('id') and __event_call__:
            await __event_call__({'type':'execute','data':{
                'code':"window.location.assign('/static/retail-learning.html#preferences');"}})
        return None
