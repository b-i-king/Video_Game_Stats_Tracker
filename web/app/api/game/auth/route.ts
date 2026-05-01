import { NextRequest, NextResponse } from 'next/server';

const BACKEND =
  process.env.FASTAPI_URL ||
  process.env.NEXT_PUBLIC_FASTAPI_URL ||
  process.env.NEXT_PUBLIC_FLASK_API_URL ||
  '';

export async function POST(req: NextRequest) {
  if (!BACKEND) {
    return NextResponse.json({ detail: 'API backend not configured.' }, { status: 503 });
  }
  try {
    const body = await req.text();
    const res = await fetch(`${BACKEND}/api/game/auth`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: 'Auth proxy error.' }, { status: 502 });
  }
}
