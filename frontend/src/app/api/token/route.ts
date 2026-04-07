import { SignJWT } from "jose";
import { NextResponse } from "next/server";

import { auth } from "@/lib/auth";

export async function GET(): Promise<NextResponse> {
  const session = await auth();

  if (!session?.user?.id) {
    return NextResponse.json({ token: null }, { status: 401 });
  }

  const secret = new TextEncoder().encode(process.env.NEXTAUTH_SECRET!);
  const token = await new SignJWT({
    sub: session.user.id,
    tier: (session as { tier?: string }).tier ?? "free",
  })
    .setProtectedHeader({ alg: "HS256" })
    .setExpirationTime("1h")
    .sign(secret);

  return NextResponse.json({ token });
}
