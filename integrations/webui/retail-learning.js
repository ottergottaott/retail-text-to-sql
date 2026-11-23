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
      status('feedback-status','Feedback received · '+result.feedback_id+' · Awaiting analyst review.');
      el('send-feedback').textContent='Feedback received';
    } catch (error) { status('feedback-status',error.message,true);el('feedback-fields').disabled=false; }
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
  loadTarget();loadPreferences();
})();
