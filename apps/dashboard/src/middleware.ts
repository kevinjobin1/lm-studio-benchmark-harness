/**
 * Auth middleware for Model Lens dashboard.
 *
 * Protects all /api/* routes (except /api/health) with JWT Bearer token
 * validation.  Also accepts ?token=<jwt> for SSE EventSource connections
 * since the EventSource API cannot set custom headers.
 *
 * Configuration:
 *   MODELLENS_SECRET — HMAC-SHA256 secret (env var or Cloudflare secret)
 *
 * Architecture:
 *   Middleware runs on every request.  Public routes (/login, /api/health,
 *   static assets) skip auth.  API routes require a valid JWT via either:
 *     - Authorization: Bearer <token> (standard API calls)
 *     - ?token=<token> query parameter (SSE EventSource connections)
 */

import { defineMiddleware } from "astro:middleware";
import * as jose from "jose";

// ── Configuration ──────────────────────────────────────────────────

/** Routes that do not require authentication. */
const PUBLIC_PATHS = new Set([
  "/login",
  "/api/health",
  "/favicon.svg",
]);

/** Cache the secret key — derived lazily. */
let _secretKey: Uint8Array | null = null;
let _warnedDefaultSecret = false;

function getSecretKey(): Uint8Array | null {
  if (!_secretKey) {
    const secret = import.meta.env.MODELLENS_SECRET;
    if (!secret || secret === "modellens-dev-secret-change-me") {
      if (!_warnedDefaultSecret) {
        console.error(
          "[modellens] WARNING: MODELLENS_SECRET is not set or using default value. " +
          "Set MODELLENS_SECRET as a Cloudflare secret for production use. " +
          "The dashboard will reject all authentication attempts until configured."
        );
        _warnedDefaultSecret = true;
      }
      return null;
    }
    _secretKey = new TextEncoder().encode(secret);
  }
  return _secretKey;
}

// ── Token extraction ───────────────────────────────────────────────

/**
 * Extract a JWT from the request.
 *
 * Checks, in order:
 *   1. ``Authorization: Bearer <token>`` header
 *   2. ``?token=<token>`` query parameter
 *
 * Returns ``null`` if no token is found.
 */
function extractToken(request: Request): string | null {
  // 1. Bearer token in Authorization header
  const authHeader = request.headers.get("Authorization");
  if (authHeader?.startsWith("Bearer ")) {
    return authHeader.slice(7);
  }

  // 2. Query parameter (for SSE EventSource connections)
  const url = new URL(request.url);
  const queryToken = url.searchParams.get("token");
  if (queryToken) {
    return queryToken;
  }

  return null;
}

// ── Token validation ──────────────────────────────────────────────

/**
 * Verify a JWT using HMAC-SHA256.
 *
 * Returns the decoded payload on success, or ``null`` if the token
 * is invalid, expired, or malformed.
 */
async function verifyToken(token: string): Promise<jose.JWTPayload | null> {
  const key = getSecretKey();
  if (!key) {
    return null; // Secret not configured — reject all tokens
  }

  try {
    const { payload } = await jose.jwtVerify(token, key, {
      algorithms: ["HS256"],
    });
    return payload;
  } catch {
    return null;
  }
}

// ── Path helpers ───────────────────────────────────────────────────

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATHS.has(pathname)) return true;
  // Static assets (CSS, JS, fonts, images) are public
  if (
    pathname.startsWith("/assets/") ||
    pathname.startsWith("/fonts/") ||
    pathname.startsWith("/_astro/") ||
    pathname.startsWith("/favicon")
  ) {
    return true;
  }
  return false;
}

// ── Middleware ─────────────────────────────────────────────────────

export const onRequest = defineMiddleware(async (context, next) => {
  const { pathname } = context.url;

  // Skip auth for public paths
  if (isPublicPath(pathname)) {
    return next();
  }

  // Only protect API routes — pages are served statically or with SSR
  // and don't contain secrets (they read from API routes that are protected).
  if (!pathname.startsWith("/api/")) {
    return next();
  }

  // Extract and verify token
  const token = extractToken(context.request);
  if (!token) {
    return new Response(
      JSON.stringify({ error: "missing_token", message: "Authorization required" }),
      {
        status: 401,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  const payload = await verifyToken(token);
  if (!payload) {
    return new Response(
      JSON.stringify({ error: "invalid_token", message: "Invalid or expired token" }),
      {
        status: 401,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  // Attach decoded payload to locals for downstream use
  context.locals.auth = {
    sub: payload.sub,
    iss: payload.iss,
    iat: payload.iat,
  };

  return next();
});
