import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

/**
 * Старые ссылки `/?project=uuid` → `/editor?project=uuid` (лендинг на `/`).
 */
export function middleware(request: NextRequest) {
  const url = request.nextUrl.clone();
  if (url.pathname === "/" && url.searchParams.has("project")) {
    url.pathname = "/editor";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/"],
};
