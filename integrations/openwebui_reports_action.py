"""
title: My reports
author: Retail assessment project
version: 0.1.0
description: Open your authenticated, current report library without a model call.
"""


class Action:
    async def action(self, body: dict, __user__: dict = None, __event_call__=None,
                     __event_emitter__=None):
        if not (__user__ or {}).get('id'):
            return None
        if __event_call__:
            # Fixed local navigation. No model/user text is interpolated as JavaScript.
            await __event_call__({'type': 'execute', 'data': {
                'code': "window.location.assign('/static/retail-reports.html');"}})
        elif __event_emitter__:
            await __event_emitter__({'type':'notification','data':{
                'type':'info','content':'Open Reports in the sidebar to view your saved reports.'}})
        return None
