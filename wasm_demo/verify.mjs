// Standalone Node.js verification that the compiled WASM module actually
// works end-to-end (loads tracker lists, cleans a URL, unwraps a
// redirector), not just that it compiled. Not part of the browser demo
// (which has its own, near-identical glue in web_demo/demo.js) -- this is
// the proof step you can run with `node wasm_demo/verify.mjs`.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const wasmPath = path.join(here, "target", "wasm32-unknown-unknown", "release", "link_scrub_wasm.wasm");
const paramsText = readFileSync(path.join(here, "..", "data", "tracking_params.txt"), "utf8");
const domainsText = readFileSync(path.join(here, "..", "data", "tracking_domains.txt"), "utf8");

const { instance } = await WebAssembly.instantiate(readFileSync(wasmPath), {});
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

function cleanUrl(url) {
    const [urlPtr, urlLen] = writeString(url);
    const outLenPtr = alloc_buffer(4);
    const resultPtr = clean(urlPtr, urlLen, outLenPtr);
    const outLen = new Uint32Array(memory.buffer, outLenPtr, 1)[0];
    const result = readString(resultPtr, outLen);
    free_buffer(urlPtr, urlLen);
    free_buffer(outLenPtr, 4);
    if (resultPtr !== 0) free_buffer(resultPtr, outLen);
    return result;
}

const cases = [
    ["https://example.com/article?utm_source=twitter&utm_medium=social&id=42", "https://example.com/article?id=42"],
    [
        "https://l.facebook.com/l.php?u=https%3A%2F%2Freal.example%2Fpath%3Futm_source%3Dnews&h=xyz",
        "https://real.example/path",
    ],
    ["https://news.ycombinator.com/item?id=12345678", "https://news.ycombinator.com/item?id=12345678"],
];

let failures = 0;
for (const [input, expected] of cases) {
    const actual = cleanUrl(input);
    const ok = actual === expected;
    if (!ok) failures++;
    console.log(`${ok ? "PASS" : "FAIL"}  ${input}\n      -> ${actual}${ok ? "" : `  (expected ${expected})`}`);
}

if (failures > 0) {
    console.error(`\n${failures} case(s) failed`);
    process.exit(1);
}
console.log("\nAll cases passed -- the WASM build of link_scrub's core works end-to-end.");
