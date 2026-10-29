// Browser glue for the static demo page. Mirrors wasm_demo/verify.mjs's
// Node glue almost exactly (same ABI, different host) -- see that file
// for a from-the-terminal proof this works, independent of a browser.
// No framework, no build step, no network calls other than fetching this
// page's own sibling files (the WASM binary + the two tracker-list .txt
// files, all staged by web_demo/build.sh).

function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

// Marks each removed param's "key=value" (or bare "key") span with a
// redaction bar, leaving the leading '?'/'&' and everything else as
// plain, escaped text. Best-effort: a param removed from inside an
// unwrapped (and therefore percent-encoded) redirector URL won't appear
// as a literal, unencoded token here, so it's silently left unmarked
// rather than guessed at.
function buildRedactedMarkup(original, removedParams) {
    if (removedParams.length === 0) return escapeHtml(original);
    const remaining = removedParams.slice();
    const tokenRe = /([?&])([^=&#]+)(=[^&#]*)?/g;
    let lastIndex = 0;
    let out = "";
    let m;
    while ((m = tokenRe.exec(original)) !== null) {
        const key = m[2];
        const idx = remaining.findIndex((p) => p.toLowerCase() === key.toLowerCase());
        if (idx === -1) continue;
        remaining.splice(idx, 1);
        const sepEnd = m.index + m[1].length;
        const tokenEnd = m.index + m[0].length;
        out += escapeHtml(original.slice(lastIndex, sepEnd));
        out += `<mark class="redacted" tabindex="0">${escapeHtml(original.slice(sepEnd, tokenEnd))}</mark>`;
        lastIndex = tokenEnd;
    }
    out += escapeHtml(original.slice(lastIndex));
    return out;
}

function row(tag, html, note) {
    return `<div class="result-row${note ? " note" : ""}"><span class="tag">${tag}</span><span class="value">${html}</span></div>`;
}

function renderResult(result) {
    const out = document.getElementById("result");
    const { original, cleaned, unwrapped_redirect, removed_params } = result;

    if (removed_params.length === 0 && !unwrapped_redirect) {
        out.innerHTML = row("", "Nothing to remove.", true);
        return;
    }

    let html = row("before", buildRedactedMarkup(original, removed_params));

    if (unwrapped_redirect) {
        let host = "";
        try {
            host = new URL(original).hostname;
        } catch {
            /* leave host blank, note still makes sense without it */
        }
        html += row("", host ? `Resolved a redirect from ${escapeHtml(host)}.` : "Resolved a wrapped redirect.", true);
    }

    html += row("after", escapeHtml(cleaned));

    if (removed_params.length > 0) {
        html += `<p class="removed-list">Removed: <b>${removed_params.map(escapeHtml).join(", ")}</b></p>`;
    }

    out.innerHTML = html;
}

async function loadTagoff() {
    const [wasmBytes, paramsText, domainsText] = await Promise.all([
        fetch("tagoff_wasm.wasm").then((r) => r.arrayBuffer()),
        fetch("data/tracking_params.txt").then((r) => r.text()),
        fetch("data/tracking_domains.txt").then((r) => r.text()),
    ]);

    const { instance } = await WebAssembly.instantiate(wasmBytes, {});
    const { memory, alloc_buffer, init_lists, clean, free_buffer } = instance.exports;

    function writeString(str) {
        const bytes = new TextEncoder().encode(str);
        const ptr = alloc_buffer(bytes.length || 1);
        new Uint8Array(memory.buffer, ptr, bytes.length).set(bytes);
        return [ptr, bytes.length];
    }

    function readString(ptr, len) {
        if (ptr === 0 || len === 0) return "";
        return new TextDecoder().decode(new Uint8Array(memory.buffer, ptr, len));
    }

    const [paramsPtr, paramsLen] = writeString(paramsText);
    const [domainsPtr, domainsLen] = writeString(domainsText);
    init_lists(paramsPtr, paramsLen, domainsPtr, domainsLen);

    return function cleanUrl(url) {
        const [urlPtr, urlLen] = writeString(url);
        const outLenPtr = alloc_buffer(4);
        const resultPtr = clean(urlPtr, urlLen, outLenPtr);
        const outLen = new Uint32Array(memory.buffer, outLenPtr, 1)[0];
        const raw = readString(resultPtr, outLen);
        free_buffer(urlPtr, urlLen);
        free_buffer(outLenPtr, 4);
        if (resultPtr !== 0) free_buffer(resultPtr, outLen);
        return JSON.parse(raw);
    };
}

const statusEl = document.getElementById("status");
const form = document.getElementById("clean-form");
const input = document.getElementById("url-input");
const button = document.getElementById("clean-button");

loadTagoff()
    .then((cleanUrl) => {
        statusEl.textContent = "";
        button.disabled = false;

        form.addEventListener("submit", (e) => {
            e.preventDefault();
            const url = input.value.trim();
            document.getElementById("result").innerHTML = "";
            if (!url) return;
            renderResult(cleanUrl(url));
        });
    })
    .catch(() => {
        statusEl.textContent = "Couldn't load. Reload the page and try again.";
        statusEl.dataset.tone = "error";
    });
