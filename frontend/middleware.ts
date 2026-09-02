import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

// Only activates Clerk's middleware when the app is actually configured
// with Clerk keys — otherwise requests pass through untouched and the
// backend's own AUTH_DEV_MODE is what's authenticating (see
// components/AuthProvider.tsx for the matching client-side fallback).
const middleware = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
  ? clerkMiddleware()
  : () => NextResponse.next();

export default middleware;

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)", "/(api|trpc)(.*)"],
};
