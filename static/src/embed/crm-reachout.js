// crm-reachout embed v0
//
// Registers <crm-reachout>: the cohort dashboard's "Reach out — from the
// CRM" card. Conventions follow the amebo embed bundle
// (amebo/embed/amebo.js): vanilla custom elements, no shadow DOM, zero
// dependencies, host page styles via the element tag selector, generic
// data-* attributes, credentialed fetches.
//
//   <script src="https://crm-<team>.workers.vc/crm_outreach_runner/static/src/embed/crm-reachout.js"></script>
//   <crm-reachout data-up="https://crm-<team>.workers.vc" data-limit="5"></crm-reachout>
//
// Attributes:
//   data-up     — the team's CRM origin (required). The component fetches
//                 {data-up}/outreach/api/queue with credentials:'include';
//                 the Odoo session cookie authenticates (SameSite=Lax,
//                 same registrable domain workers.vc).
//   data-limit  — max rows, default 5.
//
// Behavior: non-200, network error, or an empty queue → the element
// renders nothing and sets `hidden` (signed-out and non-member visitors
// just see fewer cards; never placeholder or demo data). On success it
// sets data-count="<count_to_reach>" and dispatches a bubbling
// `crm-reachout-loaded` CustomEvent with
// {count_to_reach, shown} so the host page can render the
// "CRM · N to reach" pill.
//
// All DOM writes are textContent / attribute based — no HTML
// interpolation of upstream data.

(function () {
  'use strict';
  if (window.__crmReachoutLoaded) return;
  window.__crmReachoutLoaded = true;

  function ensureStyles() {
    if (document.getElementById('crm-reachout-styles')) return;
    var s = document.createElement('style');
    s.id = 'crm-reachout-styles';
    s.textContent = [
      'crm-reachout {',
      '  display: block;',
      '  font-family: system-ui, -apple-system, sans-serif;',
      '  font-size: 14px;',
      '  color: inherit;',
      '  line-height: 1.4;',
      '}',
      'crm-reachout ul.reachout-list { list-style: none; margin: 0; padding: 0; }',
      'crm-reachout li.reachout-row {',
      '  display: flex; gap: 0.6rem; align-items: baseline;',
      '  padding: 0.45rem 0;',
      '  border-top: 1px solid rgba(127,127,127,0.15);',
      '}',
      'crm-reachout li.reachout-row:first-child { border-top: none; }',
      'crm-reachout .who { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }',
      'crm-reachout .why { flex: 1; font-size: 12px; opacity: 0.65; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }',
      'crm-reachout a.go { font-size: 12px; white-space: nowrap; opacity: 0.8; }',
      'crm-reachout a.go:hover { opacity: 1; }',
    ].join('\n');
    document.head.appendChild(s);
  }

  function upBase(el) {
    var u = el.dataset.up;
    return (u && u.replace(/\/+$/, '')) || null;
  }

  // "no reply in N days" from an ISO last_outreach_date; '' if unparseable.
  function noReplyText(iso) {
    var t = Date.parse(iso);
    if (isNaN(t)) return '';
    var days = Math.floor(Math.max(0, Date.now() - t) / 86400000);
    if (days === 0) return 'contacted today';
    return 'no reply in ' + days + (days === 1 ? ' day' : ' days');
  }

  function whyText(lead) {
    if (lead.last_outreach_date) {
      return noReplyText(lead.last_outreach_date) || (lead.outreach_score_reason || '');
    }
    return lead.outreach_score_reason || '';
  }

  // Only ever link to http(s) URLs the API handed us.
  function safeHref(url) {
    try {
      var u = new URL(url);
      if (u.protocol === 'https:' || u.protocol === 'http:') return u.href;
    } catch (e) { /* not a URL */ }
    return null;
  }

  class CrmReachout extends HTMLElement {
    async connectedCallback() {
      this.hidden = true;
      var base = upBase(this);
      if (!base) return;
      var limit = parseInt(this.dataset.limit || '5', 10);
      if (isNaN(limit) || limit < 1) limit = 5;
      var url = base + '/outreach/api/queue?limit=' + encodeURIComponent(limit);
      var data;
      try {
        var r = await fetch(url, { credentials: 'include' });
        if (!r.ok) return;
        data = await r.json();
      } catch (e) {
        // Signed-out (login redirect blocked by CORS), network error, or
        // non-JSON body: render nothing, stay hidden.
        return;
      }
      var leads = (data && Array.isArray(data.leads)) ? data.leads : [];
      if (!leads.length) return;
      this._render(leads, data.count_to_reach);
    }

    _render(leads, count) {
      ensureStyles();
      while (this.firstChild) this.removeChild(this.firstChild);
      var ul = document.createElement('ul');
      ul.className = 'reachout-list';
      for (var i = 0; i < leads.length; i++) {
        var lead = leads[i];
        var li = document.createElement('li');
        li.className = 'reachout-row';

        var who = document.createElement('span');
        who.className = 'who';
        who.textContent = lead.partner_name || lead.name || '';
        if (lead.name && lead.name !== who.textContent) {
          who.title = lead.name;
        }

        var why = document.createElement('span');
        why.className = 'why';
        why.textContent = whyText(lead);

        li.appendChild(who);
        li.appendChild(why);

        var href = safeHref(lead.url);
        if (href) {
          var a = document.createElement('a');
          a.className = 'go';
          a.textContent = 'open ↗';
          a.href = href;
          a.target = '_blank';
          a.rel = 'noopener';
          li.appendChild(a);
        }
        ul.appendChild(li);
      }
      this.appendChild(ul);
      if (typeof count === 'number') {
        this.setAttribute('data-count', String(count));
      }
      this.hidden = false;
      this.dispatchEvent(new CustomEvent('crm-reachout-loaded', {
        detail: { count_to_reach: count, shown: leads.length },
        bubbles: true,
        composed: true,
      }));
    }
  }

  if (!customElements.get('crm-reachout')) {
    customElements.define('crm-reachout', CrmReachout);
  }
})();
