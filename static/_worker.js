function error(message, status) {
  return Response.json({error: message}, {
    status,
    headers: {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);
    const method = {"/api/game": "GET", "/api/guess": "POST"}[url.pathname];
    if (!method) return error("Cette route de jeu n’existe pas.", 404);
    if (request.method !== method) return error("Cette méthode n’est pas autorisée.", 405);

    let origin;
    try {
      origin = new URL(env.GAME_API_ORIGIN);
      if (origin.protocol !== "https:" || origin.origin === url.origin || origin.username || origin.password || origin.pathname !== "/" || origin.search || origin.hash) throw new Error();
    } catch {
      return error("Le jeu n’est pas encore connecté à son serveur. Configurez GAME_API_ORIGIN dans Cloudflare Pages, puis redéployez le site.", 503);
    }

    const headers = new Headers({Accept: "application/json"});
    for (const name of ["Content-Type", "Cookie"]) {
      if (request.headers.has(name)) headers.set(name, request.headers.get(name));
    }
    try {
      const upstream = await fetch(new URL(url.pathname, origin), {
        method,
        headers,
        body: method === "POST" ? request.body : undefined,
        redirect: "manual",
        signal: AbortSignal.timeout(30000),
      });
      if (!(upstream.headers.get("Content-Type") || "").includes("application/json")) {
        return error("Le serveur du jeu a renvoyé une réponse invalide. Vérifiez l’adresse GAME_API_ORIGIN.", 502);
      }
      const responseHeaders = new Headers(upstream.headers);
      responseHeaders.set("Cache-Control", "no-store");
      responseHeaders.set("X-Content-Type-Options", "nosniff");
      // The browser keeps Flask's signed session on the public Pages domain.
      const cookies = typeof upstream.headers.getSetCookie === "function"
        ? upstream.headers.getSetCookie() : upstream.headers.getAll("Set-Cookie");
      responseHeaders.delete("Set-Cookie");
      for (const cookie of cookies) {
        const secured = cookie.replace(/;\s*Domain=[^;]*/gi, "");
        responseHeaders.append("Set-Cookie", /;\s*Secure(?:;|$)/i.test(secured) ? secured : secured + "; Secure");
      }
      return new Response(upstream.body, {status: upstream.status, headers: responseHeaders});
    } catch {
      return error("Le serveur du jeu est indisponible. Réessayez dans quelques instants.", 502);
    }
  },
};
