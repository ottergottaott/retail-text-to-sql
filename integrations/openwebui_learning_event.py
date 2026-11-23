"""
title: Retail Learning API
author: Retail assessment project
version: 0.1.0
description: Verified-user feedback, preferences and CEO tone proxy. Gates run in backend.
requirements: httpx>=0.27.0
"""
from typing import Literal
import httpx
from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from open_webui.utils.auth import get_verified_user


class FeedbackInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    external_chat_id: str = Field(min_length=1,max_length=200)
    external_message_id: str = Field(min_length=1,max_length=200)
    revision: str = Field(min_length=1,max_length=80)
    rating: Literal['helpful','unhelpful','correction']
    comment: str = Field(default='',max_length=4000)


class PreferenceInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    format: Literal['tables','bullets','prose']
    depth: Literal['concise','standard','detailed']


class ToneInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    tone: str = Field(min_length=1,max_length=2000)


class RollbackInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version: int = Field(ge=1)


class Event:
    class Valves(BaseModel):
        API_URL: str = 'http://api:8000'
        ADAPTER_SECRET: str = ''

    def __init__(self):
        self.valves=self.Valves()

    async def configuration(self, function_id):
        from open_webui.models.functions import Functions
        function=await Functions.get_function_by_id(function_id)
        if not function or not function.is_active:
            raise HTTPException(503,'Learning integration is disabled.')
        return self.Valves(**(await Functions.get_function_valves_by_id(function_id) or {}))

    async def event(self,event:dict,__event_name__:str=None,__app__=None,__id__:str=None):
        about_me=(event.get('subject') or {}).get('id')==__id__
        if __app__ is None or not (__event_name__=='system.startup.completed' or
                (__event_name__=='function.enable_started' and about_me)):
            return
        prefix='/api/retail-learning'
        if any(getattr(r,'path',None)==prefix+'/preferences' for r in __app__.routes):
            return

        async def fetch(method,path,user,body=None,params=None):
            config=await self.configuration(__id__)
            if not config.ADAPTER_SECRET:
                raise HTTPException(503,'Learning integration is not configured.')
            try:
                async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
                    response=await client.request(method,config.API_URL.rstrip('/')+path,
                        headers={'Authorization':'Bearer '+config.ADAPTER_SECRET,'X-Webui-User':user.id},
                        json=body,params=params)
            except httpx.HTTPError:
                raise HTTPException(503,'Retail service unavailable. Check saved state before retrying.') from None
            if response.status_code!=200:
                code=response.status_code if response.status_code in {401,403,404,422} else 503
                raise HTTPException(code,'Response unavailable or changed. Reload and try again.' if code in {403,404}
                    else 'Retail request could not complete.')
            try:
                value=response.json()
                if not isinstance(value,dict):raise ValueError()
                return value
            except (ValueError,TypeError):
                raise HTTPException(503,'Retail service returned an invalid response.') from None

        def output(value,fields):
            try:
                return JSONResponse({k:value[k] for k in fields},headers={'Cache-Control':'no-store'})
            except KeyError:
                raise HTTPException(503,'Retail service returned an invalid response.') from None

        async def target(external_chat_id:str,external_message_id:str,user=Depends(get_verified_user)):
            value=await fetch('GET','/webui/feedback-target',user,params={
                'external_chat_id':external_chat_id,'external_message_id':external_message_id})
            return output(value,('question','answer','revision'))

        async def feedback(body:FeedbackInput,user=Depends(get_verified_user)):
            return output(await fetch('POST','/webui/feedback',user,body.model_dump()),('feedback_id','status'))

        async def preferences(user=Depends(get_verified_user)):
            return output(await fetch('GET','/preferences',user),('format','depth','version'))

        async def save_preferences(body:PreferenceInput,user=Depends(get_verified_user)):
            return output(await fetch('PUT','/preferences',user,body.model_dump()),('format','depth','version'))

        async def feedback_status(feedback_id:str,user=Depends(get_verified_user)):
            if not feedback_id.startswith('fee_') or not feedback_id[4:].isalnum() or len(feedback_id)>80:
                raise HTTPException(422,'Invalid feedback identifier.')
            value=await fetch('GET','/feedback/'+feedback_id,user)
            return output(value,('feedback_id','status','reason','trio_id'))

        async def tone(user=Depends(get_verified_user)):
            return output(await fetch('GET','/organization/tone',user),('tone','version','can_edit','versions'))

        async def change_tone(body:ToneInput,user=Depends(get_verified_user)):
            return output(await fetch('POST','/organization/tone',user,body.model_dump()),('job_id','status'))

        async def rollback(body:RollbackInput,user=Depends(get_verified_user)):
            return output(await fetch('POST','/organization/tone/rollback',user,body.model_dump()),('version','tone'))

        async def job(job_id:str,user=Depends(get_verified_user)):
            if not job_id.startswith('aut_') or not job_id[4:].isalnum() or len(job_id)>80:
                raise HTTPException(422,'Invalid job identifier.')
            value=await fetch('GET','/automation/'+job_id,user)
            return JSONResponse({k:value[k] for k in ('status','type','attempts','reason','version') if k in value},headers={'Cache-Control':'no-store'})

        previous=len(__app__.routes)
        for path,handler,method in [('/feedback-target',target,'GET'),('/feedback',feedback,'POST'),
                ('/preferences',preferences,'GET'),('/preferences',save_preferences,'PUT'),
                ('/feedback/{feedback_id}',feedback_status,'GET'),('/organization/tone',tone,'GET'),
                ('/organization/tone',change_tone,'POST'),('/organization/tone/rollback',rollback,'POST'),
                ('/automation/{job_id}',job,'GET')]:
            __app__.add_api_route(prefix+path,handler,methods=[method])
        added=__app__.routes[previous:];del __app__.routes[previous:]
        index=next((i for i,r in enumerate(__app__.routes) if getattr(r,'path',None)==''),len(__app__.routes))
        __app__.routes[index:index]=added
