import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";

const source = await readFile(new URL("../static/_worker.js", import.meta.url), "utf8");
const {default: worker} = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
const origin = "https://game.example.com";
const request = (path, options) => new Request("https://cem-itx.pages.dev" + path, options);
const env = {GAME_API_ORIGIN: origin, ASSETS: {fetch: () => new Response("interface")}};
const originalFetch = globalThis.fetch;
try {
  assert.equal(await (await worker.fetch(request("/"), env)).text(), "interface");
  assert.equal((await worker.fetch(request("/api/game"), {})).status, 503);
  for (const badOrigin of ["https://cem-itx.pages.dev", "http://game.example.com", "https://game.example.com/?token=x", "https://user:password@game.example.com"]) {
    assert.equal((await worker.fetch(request("/api/game"), {...env, GAME_API_ORIGIN: badOrigin})).status, 503);
  }
  assert.equal((await worker.fetch(request("/api/private"), env)).status, 404);
  assert.equal((await worker.fetch(request("/api/guess"), env)).status, 405);

  globalThis.fetch = async (url, options) => {
    assert.equal(url.href, origin + "/api/game");
    assert.equal(options.headers.get("Cookie"), "session=signed-player");
    assert.equal(options.redirect, "manual");
    return Response.json({attempts: []}, {headers: {
      "Set-Cookie": "session=signed-player; Domain=game.example.com; HttpOnly; Path=/; SameSite=Lax",
      "Cache-Control": "public, max-age=3600",
    }});
  };
  const game = await worker.fetch(request("/api/game", {headers: {Cookie: "session=signed-player"}}), env);
  assert.deepEqual(await game.json(), {attempts: []});
  assert.equal(game.headers.get("Cache-Control"), "no-store");
  assert.equal(game.headers.get("Set-Cookie"), "session=signed-player; HttpOnly; Path=/; SameSite=Lax; Secure");

  globalThis.fetch = async (url, options) => {
    assert.equal(url.href, origin + "/api/guess");
    assert.equal(options.method, "POST");
    assert.deepEqual(await new Response(options.body).json(), {word: "école", day: "2026-10-07"});
    return Response.json({error: "Nouveau mot", refresh: true}, {status: 409});
  };
  const guess = await worker.fetch(request("/api/guess", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({word: "école", day: "2026-10-07"}),
  }), env);
  assert.equal(guess.status, 409);
  assert.equal((await guess.json()).refresh, true);

  for (const prefix of ["/cem-itx", "/cem-itx/"]) {
    globalThis.fetch = async (url) => {
      assert.equal(url.href, origin + "/cem-itx/api/game");
      return Response.json({day: "2026-10-07"});
    };
    assert.equal((await worker.fetch(request("/api/game"), {...env, GAME_API_ORIGIN: origin + prefix})).status, 200);
  }

  for (const action of ["register", "login", "logout"]) {
    globalThis.fetch = async (url, options) => {
      assert.equal(url.href, origin + "/api/account/" + action);
      assert.equal(options.headers.get("X-CSRF-Token"), "test-csrf");
      assert.equal(options.headers.get("Cookie"), "session=test");
      return Response.json({user: null});
    };
    assert.equal((await worker.fetch(request("/api/account/" + action, {
      method: "POST", headers: {"X-CSRF-Token": "test-csrf", Cookie: "session=test"},
    }), env)).status, 200);
  }

  globalThis.fetch = async () => new Response("<html>pas une API</html>", {headers: {"Content-Type": "text/html"}});
  assert.equal((await worker.fetch(request("/api/game"), env)).status, 502);
  globalThis.fetch = async () => {throw new Error("offline");};
  assert.equal((await worker.fetch(request("/api/game"), env)).status, 502);
  console.log("CLOUDFLARE_OK: routes, configuration, cookies, propositions, erreurs et absence de cache.");
} finally {
  globalThis.fetch = originalFetch;
}
