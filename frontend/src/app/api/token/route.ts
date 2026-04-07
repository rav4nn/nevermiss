import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const COOKIE_NAMES = [
  "__Secure-authjs.session-token",
  "authjs.session-token",
  "__Secure-next-auth.session-token",
  "next-auth.session-token",
];

export async function GET(): Promise<NextResponse> {
  const cookieStore = await cookies();

  for (const name of COOKIE_NAMES) {
    const value = cookieStore.get(name)?.value;
    if (value) {
      return NextResponse.json({ token: value });
    }
  }

  return NextResponse.json({ token: null }, { status: 401 });
}
