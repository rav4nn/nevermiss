import { getToken } from "next-auth/jwt";
import { type NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest): Promise<NextResponse> {
  const token = await getToken({
    req,
    secret: process.env.NEXTAUTH_SECRET!,
    // Must match the custom encode in auth.ts — raw JWT, not encrypted JWE
    raw: true,
  });

  if (!token) {
    return NextResponse.json({ token: null }, { status: 401 });
  }

  return NextResponse.json({ token });
}
