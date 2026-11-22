/* v0.13.4 sidebar overlay. No session access; inserts one fixed same-origin link. */
(() => {
  'use strict';
  function install() {
    let references = document.querySelectorAll('a[href="/notes"]');
    if (!references.length) references = document.querySelectorAll('a[href="/workspace"]');
    if (!references.length) references = document.querySelectorAll('a#sidebar-new-chat-button');
    references.forEach((reference, index) => {
      if (document.getElementById('retail-reports-nav-' + index)) return;
      const link = document.createElement('a');
      link.dataset.retailReportsNav = 'true'; link.id = 'retail-reports-nav-' + index;
      link.href = '/static/retail-reports.html';
      link.setAttribute('data-sveltekit-reload', '');
      link.addEventListener('click', event => {
        if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault(); event.stopPropagation(); window.location.assign(link.href);
      });
      link.className = reference.className; link.title = 'Reports'; link.setAttribute('aria-label', 'Reports');
      const icon = document.createElement('span'); icon.textContent = '▤'; icon.setAttribute('aria-hidden', 'true'); icon.style.fontSize = '20px';
      const label = document.createElement('span'); label.textContent = 'Reports';
      if (!reference.textContent.trim()) label.className = 'sr-only';
      link.append(icon, label);
      const row = document.createElement('div'); row.className = reference.parentElement.className;
      row.append(link); reference.parentElement.after(row);
    });
  }
  let scheduled = false;
  const observer = new MutationObserver(() => {
    if (scheduled) return;
    scheduled = true; requestAnimationFrame(() => { scheduled = false; install(); });
  });
  observer.observe(document.documentElement, {childList:true,subtree:true});
  install();
})();
