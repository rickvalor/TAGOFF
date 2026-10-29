// Browser glue for the static demo page. Mirrors wasm_demo/verify.mjs's
// Node glue almost exactly (same ABI, different host) -- see that file
// for a from-the-terminal proof this works, independent of a browser.
// No framework, no build step, no network calls other than fetching this
// page's own sibling files (the WASM binary + the two tracker-list .txt
// files, all staged by web_demo/build.sh).

async function loadLinkScrub() {
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
        const result = readString(resultPtr, outLen);
        free_buffer(urlPtr, urlLen);
        free_buffer(outLenPtr, 4);
        if (resultPtr !== 0) free_buffer(resultPtr, outLen);
        return result;
    };
}

loadLinkScrub()
    .then((cleanUrl) => {
        const input = document.getElementById("url-input");
        const button = document.getElementById("clean-button");
        const output = document.getElementById("output");
        const status = document.getElementById("status");

        status.textContent = "Ready -- running entirely in this tab, no network calls beyond loading this page.";
        button.disabled = false;

        function run() {
            const url = input.value.trim();
            if (!url) {
                output.textContent = "";
                return;
            }
            output.textContent = cleanUrl(url);
        }

        button.addEventListener("click", run);
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") run();
        });
    })
    .catch((err) => {
        document.getElementById("status").textContent = "Failed to load: " + err;
    });
