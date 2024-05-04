import { NextRequest, NextResponse } from 'next/server'

export function middleware(request: NextRequest) {
    if (!request.headers.get('Authorization')) {
        return NextResponse.redirect(new URL('/api/auth/unauthorized', request.url));
    }
}

export const config = {
    matcher: [
        '/api/bilibili/sess',
        '/api/tencent/:path*',
        '/api/agora/:path*',
    ],
}
