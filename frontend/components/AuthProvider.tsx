"use client";

import { ClerkProvider, useAuth as useClerkAuth } from "@clerk/nextjs";
import { createContext, useContext, type ReactNode } from "react";

interface AppAuth {
  getToken: () => Promise<string | null>;
  isSignedIn: boolean;
  isDevMode: boolean;
}

const DevAuthContext = createContext<AppAuth>({
  getToken: async () => null,
  isSignedIn: true,
  isDevMode: true,
});

const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

/**
 * `publishableKey` is a build-time environment constant — identical on
 * every render of a given deployment — so branching a hook call on it
 * never changes across renders within that build and doesn't trigger
 * React's "hooks called in a different order" failure mode. This is what
 * lets the whole app run without any Clerk configuration (dev mode, backed
 * by the API's own `AUTH_DEV_MODE`) and with real Clerk auth from the same
 * code once `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is set — never a fake
 * "signed in" UI pretending Clerk is wired when it isn't.
 */
export function useAppAuth(): AppAuth {
  if (publishableKey) {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { getToken, isSignedIn } = useClerkAuth();
    return { getToken: async () => getToken(), isSignedIn: !!isSignedIn, isDevMode: false };
  }
  // eslint-disable-next-line react-hooks/rules-of-hooks
  return useContext(DevAuthContext);
}

export function AppAuthProvider({ children }: { children: ReactNode }) {
  if (publishableKey) {
    return <ClerkProvider publishableKey={publishableKey}>{children}</ClerkProvider>;
  }
  return <DevAuthContext.Provider value={{ getToken: async () => null, isSignedIn: true, isDevMode: true }}>{children}</DevAuthContext.Provider>;
}

export const isClerkConfigured = !!publishableKey;
