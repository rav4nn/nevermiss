import NextAuth, { type DefaultSession } from "next-auth";
import { type JWT } from "next-auth/jwt";
import Google from "next-auth/providers/google";

// Extend the built-in session/token types with our custom fields.
declare module "next-auth" {
  interface Session extends DefaultSession {
    user: DefaultSession["user"] & { id: string };
    tier: "free" | "pro";
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    tier?: "free" | "pro";
  }
}

const GOOGLE_SCOPES = [
  "openid",
  "email",
  "profile",
  "https://www.googleapis.com/auth/gmail.readonly",
  "https://www.googleapis.com/auth/calendar.events",
].join(" ");

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
      authorization: {
        params: {
          scope: GOOGLE_SCOPES,
          // offline access is required to receive a refresh_token.
          access_type: "offline",
          // prompt=consent forces the consent screen on every sign-in,
          // which guarantees Google issues a refresh_token even for returning users.
          prompt: "consent",
        },
      },
    }),
  ],

  callbacks: {
    async jwt({ token, account }) {
      // `account` is only populated on the first sign-in (OAuth callback).
      if (account) {
        if (!account.refresh_token || !account.access_token) {
          // This should not happen with prompt=consent + access_type=offline,
          // but guard defensively. Without a refresh_token the backend cannot
          // scan Gmail, so we log and return without setting userId.
          console.error(
            "[auth] Google did not return refresh_token or access_token.",
          );
          return token;
        }

        const expiresAt = account.expires_at
          ? new Date(account.expires_at * 1000).toISOString()
          : new Date(Date.now() + 3_600_000).toISOString();

        // POST tokens to the backend for encrypted storage.
        // The tokens are NOT stored in the NextAuth cookie after this point.
        try {
          const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "";
          const res = await fetch(`${apiUrl}/api/auth/session`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              googleSub: account.providerAccountId,
              email: token.email,
              gmailAddress: token.email,
              refreshToken: account.refresh_token,
              accessToken: account.access_token,
              accessTokenExpiresAt: expiresAt,
              // Default to UTC. Users can update their timezone in /settings.
              timezone: "UTC",
            }),
          });

          if (res.ok) {
            const user = (await res.json()) as { id: string; tier: "free" | "pro" };
            // Override sub with our internal UUID.
            // The backend's get_current_user dependency reads token.sub as the user UUID.
            token.sub = user.id;
            token.tier = user.tier;
          } else {
            const body = await res.text();
            console.error("[auth] Backend session sync failed", res.status, body);
          }
        } catch (err) {
          console.error("[auth] Backend session sync error", err);
        }
      }

      return token;
    },

    async session({ session, token }) {
      // Expose only non-sensitive claims in the session cookie.
      // Never put tokens, refresh tokens, or API keys here.
      if (token.sub) {
        session.user.id = token.sub;
      }
      session.tier = token.tier ?? "free";
      return session;
    },
  },

  // NextAuth v5 uses JWE (encrypted) tokens by default, but the FastAPI backend
  // verifies plain HS256 JWTs. Override encode/decode to emit signed-only tokens
  // using the same NEXTAUTH_SECRET so both sides can verify.
  jwt: {
    async encode({ token, secret }) {
      const { SignJWT } = await import("jose");
      const secretKey = new TextEncoder().encode(
        Array.isArray(secret) ? secret[0] : secret,
      );
      return new SignJWT(token as Record<string, unknown>)
        .setProtectedHeader({ alg: "HS256" })
        .sign(secretKey);
    },

    async decode({ token, secret }) {
      if (!token) return null;
      const { jwtVerify } = await import("jose");
      const secretKey = new TextEncoder().encode(
        Array.isArray(secret) ? secret[0] : secret,
      );
      const { payload } = await jwtVerify(token, secretKey, {
        algorithms: ["HS256"],
      });
      return payload as JWT;
    },
  },

  pages: {
    signIn: "/login",
  },
});
