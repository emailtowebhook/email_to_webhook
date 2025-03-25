/**
 * Basic Cloudflare Worker Template
 *
 * This template demonstrates:
 * - Request handling
 * - Environment variables
 * - KV storage access (if configured)
 * - Caching
 * - API routes with different HTTP methods
 */

// Define routes for the API
const routes = {
  "/api/hello": handleHello,
  "/api/echo": handleEcho,
  "/api/cache": handleCache,
  "/api/kv": handleKV,
  "/": handleHome,
};

export default {
  /**
   * Main fetch handler for the Worker
   */
  async fetch(request, env, ctx) {
    try {
      // Parse request URL
      const url = new URL(request.url);
      const path = url.pathname;
      const method = request.method;

      // Log the request (you'll see this in the Cloudflare Worker logs)
      console.log(`Handling ${method} request to ${path}`);

      // Find the appropriate route handler
      for (const [route, handler] of Object.entries(routes)) {
        if (path.startsWith(route)) {
          return await handler(request, env, ctx);
        }
      }

      // If no route matches, return 404
      return new Response("Not Found", { status: 404 });
    } catch (error) {
      // Log any errors
      console.error(`Error processing request: ${error.message}`);
      return new Response(`Error: ${error.message}`, { status: 500 });
    }
  },
};

/**
 * Simple "Hello World" handler
 */
async function handleHome(request, env, ctx) {
  return new Response(
    `
    <!DOCTYPE html>
    <html>
      <head>
        <title>Cloudflare Worker Demo</title>
        <style>
          body { font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; }
          h1 { color: #F6821F; }
          .endpoint { background: #f4f4f4; padding: 1rem; border-radius: 4px; margin-bottom: 1rem; }
          code { font-family: monospace; background: #e4e4e4; padding: 2px 4px; border-radius: 2px; }
        </style>
      </head>
      <body>
        <h1>Cloudflare Worker API Demo</h1>
        <p>This worker demonstrates basic Cloudflare Worker functionality.</p>
        
        <h2>Available Endpoints</h2>
        
        <div class="endpoint">
          <h3>GET /api/hello</h3>
          <p>Returns a simple greeting with some request information.</p>
        </div>
        
        <div class="endpoint">
          <h3>POST /api/echo</h3>
          <p>Echoes back any JSON or text you send in the request body.</p>
        </div>
        
        <div class="endpoint">
          <h3>GET /api/cache</h3>
          <p>Demonstrates caching with <code>Cache-Control</code> headers.</p>
        </div>
        
        <div class="endpoint">
          <h3>GET/PUT /api/kv</h3>
          <p>If KV binding is configured, demonstrates reading/writing to KV storage.</p>
        </div>
      </body>
    </html>
  `,
    {
      headers: { "Content-Type": "text/html" },
    }
  );
}

/**
 * API handler for /api/hello
 */
async function handleHello(request, env, ctx) {
  const name = new URL(request.url).searchParams.get("name") || "World";

  const data = {
    message: `Hello, ${name}!`,
    timestamp: new Date().toISOString(),
    cf: request.cf
      ? {
          country: request.cf.country,
          city: request.cf.city,
          region: request.cf.region,
          colo: request.cf.colo,
        }
      : "CF data not available",
  };

  return new Response(JSON.stringify(data, null, 2), {
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * API handler for /api/echo - echoes back request data
 */
async function handleEcho(request, env, ctx) {
  if (request.method !== "POST") {
    return new Response("Method not allowed. Use POST.", { status: 405 });
  }

  let responseData;
  const contentType = request.headers.get("Content-Type") || "";

  if (contentType.includes("application/json")) {
    // Parse JSON request
    try {
      responseData = await request.json();
    } catch (e) {
      return new Response("Invalid JSON", { status: 400 });
    }
  } else {
    // Handle text or other formats
    responseData = {
      text: await request.text(),
      headers: Object.fromEntries([...request.headers.entries()]),
      method: request.method,
    };
  }

  return new Response(JSON.stringify(responseData, null, 2), {
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * API handler for /api/cache - demonstrates caching
 */
async function handleCache(request, env, ctx) {
  const cacheKey = new URL(request.url).toString();

  // Try to get from cache
  const cache = caches.default;
  let response = await cache.match(cacheKey);

  if (!response) {
    console.log("Cache miss - generating new response");

    // Generate data that would typically be expensive to calculate
    const data = {
      timestamp: new Date().toISOString(),
      random: Math.random(),
      message: "This response is cached for 30 seconds",
    };

    response = new Response(JSON.stringify(data, null, 2), {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "public, max-age=30",
        "X-Cache": "MISS",
      },
    });

    // Store in cache
    ctx.waitUntil(cache.put(cacheKey, response.clone()));
  } else {
    console.log("Cache hit");
    // Create a new response with the cached body but updated headers
    const cachedBody = await response.text();
    response = new Response(cachedBody, {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "public, max-age=30",
        "X-Cache": "HIT",
      },
    });
  }

  return response;
}

/**
 * API handler for /api/kv - demonstrates KV storage
 */
async function handleKV(request, env, ctx) {
  // Check if KV binding is configured
  const kv = env.MY_KV;
  if (!kv) {
    return new Response(
      JSON.stringify({
        error: "KV binding not configured",
        message:
          "Add a KV namespace binding named 'MY_KV' in your worker configuration",
      }),
      {
        status: 501,
        headers: { "Content-Type": "application/json" },
      }
    );
  }

  const key = new URL(request.url).searchParams.get("key") || "default-key";

  // Handle GET requests (read from KV)
  if (request.method === "GET") {
    const value = await kv.get(key);
    return new Response(
      JSON.stringify({
        key: key,
        value: value || null,
        found: value !== null,
      }),
      {
        headers: { "Content-Type": "application/json" },
      }
    );
  }

  // Handle PUT requests (write to KV)
  if (request.method === "PUT") {
    let value;
    try {
      const body = await request.json();
      value = body.value;
    } catch (e) {
      return new Response('Invalid JSON. Send: {"value": "your-value"}', {
        status: 400,
      });
    }

    if (value === undefined) {
      return new Response('Missing "value" field in JSON', { status: 400 });
    }

    await kv.put(key, value);
    return new Response(
      JSON.stringify({
        key: key,
        value: value,
        success: true,
      }),
      {
        headers: { "Content-Type": "application/json" },
      }
    );
  }

  return new Response("Method not allowed. Use GET or PUT.", { status: 405 });
}
