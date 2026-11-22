import assert from "node:assert/strict";
import { test } from "node:test";

import { apiUrl, runtimeConfigScript } from "./api-url.ts";

function withEnv(vars: Record<string, string | undefined>, run: () => void) {
  const saved = Object.fromEntries(Object.keys(vars).map((k) => [k, process.env[k]]));
  for (const [k, v] of Object.entries(vars)) {
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
  try {
    run();
  } finally {
    for (const [k, v] of Object.entries(saved)) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
  }
}

test("server rendering prefers the internal URL, then the public one", () => {
  withEnv({ QANOUN_API_URL: "http://api:8000", QANOUN_PUBLIC_API_URL: "https://api.example.ma" }, () =>
    assert.equal(apiUrl(), "http://api:8000"),
  );
  withEnv({ QANOUN_API_URL: undefined, QANOUN_PUBLIC_API_URL: "https://api.example.ma" }, () =>
    assert.equal(apiUrl(), "https://api.example.ma"),
  );
});

test("without runtime variables it falls back to the build-time URL", () => {
  withEnv({ QANOUN_API_URL: undefined, QANOUN_PUBLIC_API_URL: undefined }, () =>
    assert.equal(apiUrl(), process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"),
  );
});

test("the runtime config script cannot close its own script element", () => {
  const script = runtimeConfigScript('https://x.ma/</script><script>alert(1)</script>');
  assert.ok(!script.includes("</script"));
  const window: { __QANOUN_API_URL__?: string } = {};
  new Function("window", script)(window);
  assert.equal(window.__QANOUN_API_URL__, "https://x.ma/</script><script>alert(1)</script>");
});
