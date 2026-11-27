import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/lib/api.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { apiFetch } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
globalThis.localStorage = { getItem: () => null, removeItem: () => {} };
globalThis.window = { setTimeout, clearTimeout, location: { pathname: "/employees" } };

test("a stalled request times out instead of leaving the capture busy forever", async () => {
  globalThis.fetch = (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
  });
  await assert.rejects(apiFetch("/capture", { timeoutMs: 10 }), /demorou demais/);
});

test("closing the capture preserves caller cancellation", async () => {
  const controller = new AbortController();
  globalThis.fetch = (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
  });
  const pending = apiFetch("/capture", { signal: controller.signal });
  controller.abort();
  await assert.rejects(pending, { name: "AbortError" });
});

test("proxy errors are readable even when the server returns HTML", async () => {
  globalThis.fetch = async () => new Response("<html>Gateway timeout</html>", { status: 504 });
  await assert.rejects(apiFetch("/capture"), /HTTP 504/);
});

test("successful capture results are preserved", async () => {
  globalThis.fetch = async () => Response.json({ accepted: true });
  assert.deepEqual(await apiFetch("/capture"), { accepted: true });
});
