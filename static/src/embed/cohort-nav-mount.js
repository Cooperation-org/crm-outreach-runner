/** @odoo-module **/

// The cohort's cross-app bar, on top of this team's CRM.
//
// A person working in crm-<org>.workers.vc is inside the cohort, and Odoo gives
// them no way back to the dash, the board, or their org. workers.vc owns the bar
// and serves the script; this addon only mounts it and gets out of the way.
//
// Only a signed-in person sees it, twice over: this bundle is served to an
// authenticated backend session only (the login page is a different bundle),
// and the bar itself draws its links only once GovKit confirms the person is in
// the cohort. Unset `cohort_nav.src` and nothing here runs at all.
//
// The org is read off the hostname because that is what the cohort's own routing
// already encodes — crm-wayfern.workers.vc IS the wayfern CRM. Nothing is
// guessed: a host that does not match leaves the slug off, and the bar falls
// back to the places that need no org.

import { session } from "@web/session";

const BAR_HEIGHT = 32;

function orgFromHost(host) {
    const m = /^crm-([a-z0-9-]+)\./.exec(host);
    return m ? m[1] : "";
}

function mount(src) {
    if (document.querySelector("cohort-nav")) {
        return;
    }
    // Odoo's web client is sized to the full viewport, so the bar cannot simply
    // be prepended: it has to take its 32px out of the client's height, or the
    // page grows a scrollbar it never had.
    const style = document.createElement("style");
    style.textContent = `
        body > cohort-nav { position: relative; z-index: 1000; background: var(--o-webclient-bg, #fff); }
        body > .o_web_client { height: calc(100vh - ${BAR_HEIGHT}px); }
    `;
    document.head.appendChild(style);

    const nav = document.createElement("cohort-nav");
    const org = orgFromHost(window.location.hostname);
    if (org) {
        nav.dataset.org = org;
    }
    nav.dataset.current = "crm";
    document.body.prepend(nav);

    const s = document.createElement("script");
    s.src = src;
    s.defer = true;
    document.head.appendChild(s);
}

const src = session.cohort_nav_src;
if (src) {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => mount(src), { once: true });
    } else {
        mount(src);
    }
}
