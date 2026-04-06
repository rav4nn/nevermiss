import { handlers } from "@/lib/auth";

// NextAuth v5 App Router handler.
// GET handles the OAuth callback and session reads.
// POST handles sign-in/sign-out form actions.
export const { GET, POST } = handlers;
