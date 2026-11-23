/* Preference inspection/override/reset. Credentials never enter URLs or model context. */
(() => {
  'use strict';
  const el = id => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const reference = {external_chat_id:params.get('chat'), external_message_id:params.get('message')};
  let revision = null;
  function status(id,message,error=false) { el(id).textContent=message; el(id).className=error?'error':'success'; }
  async function api(path,method='GET',body) {
    const token=localStorage.getItem('token');
    if (!token) throw new Error('Sign in to Open WebUI, then return to this page.');
    let response;
    try {
      response=await fetch('/api/retail-learning'+path,{method,cache:'no-store',
        headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},
        body:body===undefined?undefined:JSON.stringify(body)});
    } catch (_) { throw new Error('Connection interrupted. Your submission may have arrived; avoid repeated submissions.'); }
    if (!response.ok) throw new Error(response.status===401?'Your session expired. Sign in again.':
      [403,404].includes(response.status)?'This response is unavailable or has changed. Reopen feedback from the chat. Older responses may not have a feedback reference.':
      'The retail service could not complete this request. Please try again later.');
    return response.json();
  }
  if (reference.external_chat_id) el('back-chat').href='/c/'+encodeURIComponent(reference.external_chat_id);
  async function loadTarget() {
    if (!reference.external_chat_id || !reference.external_message_id) {
      status('target-status','To give feedback, use Give feedback under a Retail Intelligence response.');
      return;
    }
    try {
      const target=await api('/feedback-target?'+new URLSearchParams(reference));
      revision=target.revision;el('question').textContent=target.question;el('answer').textContent=target.answer;
      el('response-preview').hidden=false;el('feedback-fields').disabled=false;
      status('target-status','Response loaded. Your feedback will be linked to this answer.');
    } catch (error) { status('target-status',error.message,true); }
  }
  el('feedback-form').addEventListener('submit',async event => {
    event.preventDefault();
    if (!revision) return;
    const rating=new FormData(event.target).get('rating');
    if (!rating) return;
    el('feedback-fields').disabled=true;status('feedback-status','Sending feedback…');
    try {
      const result=await api('/feedback','POST',{...reference,revision,rating,comment:el('comment').value});
      status('feedback-status','Feedback received · Automatic checks pending.');
      pollFeedback(result.feedback_id);
      el('send-feedback').textContent='Feedback received';
    } catch (error) { status('feedback-status',error.message,true);el('feedback-fields').disabled=false; }
  });
  async function pollFeedback(id,attempt=0) {
    try {
      const value=await api('/feedback/'+encodeURIComponent(id));
      if (value.status==='published') {status('feedback-status','Applied · This validated example is now available to authorized future queries.');return;}
      if (['rejected','failed'].includes(value.status)) {status('feedback-status','Feedback retained · '+(value.reason||'Not promoted to knowledge.'));return;}
      status('feedback-status',value.status==='retry_pending'?'Feedback retained · Evaluation unavailable; retry scheduled.':'Feedback received · Automatic checks pending.');
      if (attempt<90) setTimeout(()=>pollFeedback(id,attempt+1),2000);
    } catch (_) {status('feedback-status','Feedback received. Status is temporarily unavailable.');}
  }
  async function loadTone() {
    try {
      const value=await api('/organization/tone');
      if (!value.can_edit) return;
      el('organization-tone').hidden=false;
      el('tone-current').textContent='Active version '+value.version+' · '+value.tone;
      el('tone-text').value=value.tone;
      el('tone-version').replaceChildren(...value.versions.map(v=>{
        const option=document.createElement('option');option.value=v.version;option.textContent='Version '+v.version;return option;
      }));
      el('tone-rollback').disabled=!value.versions.length;
    } catch (_) { /* Personal settings stay available if organization settings cannot load. */ }
  }
  async function pollTone(id,attempt=0) {
    try {
      const value=await api('/automation/'+encodeURIComponent(id));
      if (value.status==='activated') {status('tone-status','Applied automatically · version '+value.version);el('tone-submit').disabled=false;loadTone();return;}
      if (['rejected','failed','superseded'].includes(value.status)) {status('tone-status',value.reason||'Gate failed. Previous tone retained.',true);el('tone-submit').disabled=false;return;}
      if (attempt<90) setTimeout(()=>pollTone(id,attempt+1),2000);
      else {status('tone-status','Evaluation remains pending. The current tone stays active.');el('tone-submit').disabled=false;}
    } catch (error) {status('tone-status',error.message,true);el('tone-submit').disabled=false;}
  }
  el('tone-form').addEventListener('submit',async event=>{
    event.preventDefault();el('tone-submit').disabled=true;status('tone-status','Queued for automatic evaluation…');
    try {const value=await api('/organization/tone','POST',{tone:el('tone-text').value});pollTone(value.job_id);}
    catch (error) {status('tone-status',error.message,true);el('tone-submit').disabled=false;}
  });
  el('tone-rollback').addEventListener('click',async()=>{
    try {const value=await api('/organization/tone/rollback','POST',{version:Number(el('tone-version').value)});status('tone-status','Restored as version '+value.version);loadTone();}
    catch (error) {status('tone-status',error.message,true);}
  });
  function setPreferences(value) { el('format').value=value.format;el('depth').value=value.depth; }
  async function loadPreferences() {
    try {
      const value=await api('/preferences');setPreferences(value);el('preference-fields').disabled=false;
      status('preference-status','Current account preferences · version '+value.version+
        (value.source==='learned'?' · Learned from repeated presentation requests.':' · Explicit settings or defaults.'));
    } catch (error) { status('preference-status',error.message,true); }
  }
  async function savePreferences(value) {
    el('preference-fields').disabled=true;status('preference-status','Saving preferences…');
    try {
      const result=await api('/preferences','PUT',value);setPreferences(result);
      status('preference-status','Saved to your account · version '+result.version+' · Applies in new conversations too.');
    } catch (error) { status('preference-status',error.message,true); }
    finally { el('preference-fields').disabled=false; }
  }
  el('preferences-form').addEventListener('submit',event=>{
    event.preventDefault();savePreferences({format:el('format').value,depth:el('depth').value});
  });
  el('reset-preferences').addEventListener('click',()=>savePreferences({format:'tables',depth:'standard'}));
  loadTarget();loadPreferences();loadTone();
})();
