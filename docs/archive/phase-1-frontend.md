# PuckLogic Phase 1 — Frontend Implementation

## Foundation — Auth Shell, Protected Routes, and Dashboard Skeleton

**Timeline:** March – April 2026 (Phase 1)
**Target Release:** v1.0 (September 2026)
**Backend Reference:** `docs/phase-1-backend.md`

---

## Overview

Phase 1 frontend establishes the **auth shell**: login and signup pages using Supabase Auth UI, middleware-based route protection, an empty dashboard skeleton with navigation, and Zustand store scaffolding. No data is displayed yet — this phase proves the auth pipeline end-to-end.

**Deliverables:**
1. ✅ Next.js 14+ App Router scaffold (already in place from Turborepo init)
2. ✅ Supabase Auth UI (`@supabase/auth-ui-react`) — login + signup pages
3. ✅ Auth context / Supabase client setup (`@supabase/ssr`)
4. ✅ Protected route layout — `/dashboard/*` redirects to `/login` if no session
5. ✅ Empty dashboard shell (header, sidebar nav, main content area)
6. ✅ Tailwind CSS + shadcn/ui global setup
7. ✅ Test coverage (Vitest + React Testing Library)

---

## 1. Supabase Client Setup

### 1.1 Browser Client

**Location:** `apps/web/src/lib/supabase.ts`

```typescript
import { createBrowserClient } from "@supabase/ssr";
import type { Database } from "@/types/supabase";

export const supabase = createBrowserClient<Database>(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);
```

Used in Client Components and browser-side hooks.

### 1.2 Server Client Factory

**Location:** `apps/web/src/lib/supabase-server.ts`

```typescript
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import type { Database } from "@/types/supabase";

export function createSupabaseServerClient() {
  const cookieStore = cookies();
  return createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        get(name) { return cookieStore.get(name)?.value; },
        set(name, value, options) { cookieStore.set({ name, value, ...options }); },
        remove(name, options) { cookieStore.set({ name, value: "", ...options }); },
      },
    }
  );
}
```

Used in Server Components, Server Actions, and Route Handlers.

---

## 2. Route Structure

```
apps/web/src/app/
  (auth)/
    login/
      page.tsx          # Supabase Auth UI login form
    signup/
      page.tsx          # Supabase Auth UI signup form
    callback/
      route.ts          # OAuth callback — exchanges code for session
  (dashboard)/
    layout.tsx          # Protected layout — redirects to /login if no session
    dashboard/
      page.tsx          # Empty dashboard shell
    settings/
      page.tsx          # User settings (stub)
  layout.tsx            # Root layout — fonts, global providers
  page.tsx              # Marketing landing page → redirects to /dashboard if authed
middleware.ts           # Session refresh + route protection
```

Route groups `(auth)` and `(dashboard)` are Next.js conventions — they don't appear in URLs.

---

## 3. Auth Pages

### 3.1 Login Page

**Location:** `apps/web/src/app/(auth)/login/page.tsx`

```tsx
"use client";

import { Auth } from "@supabase/auth-ui-react";
import { ThemeSupa } from "@supabase/auth-ui-shared";
import { supabase } from "@/lib/supabase";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-sm space-y-4 p-6">
        <h1 className="text-2xl font-bold text-center">PuckLogic</h1>
        <p className="text-muted-foreground text-center text-sm">Sign in to your draft kit</p>
        <Auth
          supabaseClient={supabase}
          appearance={{ theme: ThemeSupa }}
          providers={["google"]}
          redirectTo={`${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback`}
          view="sign_in"
        />
      </div>
    </div>
  );
}
```

### 3.2 Signup Page

**Location:** `apps/web/src/app/(auth)/signup/page.tsx`

Same structure as login, with `view="sign_up"` passed to the `Auth` component.

### 3.3 OAuth Callback Route Handler

**Location:** `apps/web/src/app/(auth)/callback/route.ts`

```typescript
import { NextRequest, NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase-server";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  if (code) {
    const supabase = createSupabaseServerClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}/dashboard`);
    }
  }

  return NextResponse.redirect(`${origin}/login?error=auth_failed`);
}
```

---

## 4. Middleware (Route Protection)

**Location:** `apps/web/middleware.ts`

```typescript
import { createServerClient } from "@supabase/ssr";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export async function middleware(request: NextRequest) {
  let response = NextResponse.next({
    request: { headers: request.headers },
  });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        get(name) { return request.cookies.get(name)?.value; },
        set(name, value, options) {
          request.cookies.set({ name, value, ...options });
          response.cookies.set({ name, value, ...options });
        },
        remove(name, options) {
          request.cookies.set({ name, value: "", ...options });
          response.cookies.set({ name, value: "", ...options });
        },
      },
    }
  );

  // Refresh session — extends cookie TTL on each request
  const { data: { session } } = await supabase.auth.getSession();

  const isDashboardRoute = request.nextUrl.pathname.startsWith("/dashboard");
  if (isDashboardRoute && !session) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  return response;
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
```

---

## 5. Dashboard Shell

### 5.1 Protected Layout

**Location:** `apps/web/src/app/(dashboard)/layout.tsx`

```tsx
import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase-server";
import { AppHeader } from "@/components/AppHeader";
import { Sidebar } from "@/components/Sidebar";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = createSupabaseServerClient();
  const { data: { session } } = await supabase.auth.getSession();

  if (!session) {
    redirect("/login");
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <AppHeader user={session.user} />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
```

### 5.2 AppHeader Component

**Location:** `apps/web/src/components/AppHeader.tsx`

```tsx
"use client";

import type { User } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

interface AppHeaderProps {
  user: User;
}

export function AppHeader({ user }: AppHeaderProps) {
  const router = useRouter();

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.push("/login");
  }

  return (
    <header className="flex h-14 items-center justify-between border-b px-6">
      <span className="font-semibold text-lg">PuckLogic</span>
      <div className="flex items-center gap-3">
        <Avatar className="h-8 w-8">
          <AvatarFallback>{user.email?.[0].toUpperCase()}</AvatarFallback>
        </Avatar>
        <Button variant="ghost" size="sm" onClick={handleSignOut}>
          Sign out
        </Button>
      </div>
    </header>
  );
}
```

### 5.3 Sidebar Component

**Location:** `apps/web/src/components/Sidebar.tsx`

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  TableCellsIcon,
  ChartBarIcon,
  ArrowDownTrayIcon,
  Cog6ToothIcon,
} from "@heroicons/react/24/outline";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Rankings", icon: TableCellsIcon },
  { href: "/dashboard/trends", label: "Trends", icon: ChartBarIcon },
  { href: "/dashboard/exports", label: "Exports", icon: ArrowDownTrayIcon },
  { href: "/dashboard/settings", label: "Settings", icon: Cog6ToothIcon },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 border-r bg-background flex flex-col gap-1 p-3">
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          className={cn(
            "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent",
            pathname === href && "bg-accent text-accent-foreground"
          )}
        >
          <Icon className="h-4 w-4" />
          {label}
        </Link>
      ))}
    </aside>
  );
}
```

---

## 6. Zustand Store (Phase 1 Stub)

**Location:** `apps/web/src/store/index.ts`

Phase 1 initializes the store with only the auth slice. Additional slices (rankings, trends, kits) are added in Phases 2 and 3.

```typescript
import { create } from "zustand";
import type { User } from "@supabase/supabase-js";

export interface AuthState {
  user: User | null;
  setUser: (user: User | null) => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
  user: null,
  setUser: (user) => set({ user }),
}));
```

---

## 7. Global Setup

### 7.1 Tailwind Configuration

**Location:** `apps/web/tailwind.config.ts`

Extends the default Tailwind config with shadcn/ui CSS variables:

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
    "../../packages/ui/src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        // ... other shadcn/ui tokens
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
```

### 7.2 Root Layout

**Location:** `apps/web/src/app/layout.tsx`

```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "PuckLogic — Fantasy Hockey Draft Kit",
  description: "Consensus rankings and real-time draft monitor for fantasy hockey.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>{children}</body>
    </html>
  );
}
```

---

## 8. Testing

### 8.1 Test Configuration

**Location:** `apps/web/vitest.config.ts`

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      thresholds: { lines: 80 },
    },
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
});
```

**Location:** `apps/web/src/test/setup.ts`

```typescript
import "@testing-library/jest-dom";
```

### 8.2 Key Test Cases

```tsx
// src/app/(auth)/login/__tests__/page.test.tsx

import { render, screen } from "@testing-library/react";
import LoginPage from "../page";

vi.mock("@supabase/auth-ui-react", () => ({
  Auth: () => <div data-testid="auth-ui">Auth UI</div>,
}));

vi.mock("@/lib/supabase", () => ({
  supabase: {},
}));

test("renders login heading and Auth UI", () => {
  render(<LoginPage />);
  expect(screen.getByText("PuckLogic")).toBeInTheDocument();
  expect(screen.getByTestId("auth-ui")).toBeInTheDocument();
});


// src/components/__tests__/AppHeader.test.tsx

import { render, screen, fireEvent } from "@testing-library/react";
import { AppHeader } from "../AppHeader";

const mockUser = { email: "test@example.com", id: "uuid-123" } as any;
const mockSignOut = vi.fn().mockResolvedValue({});
const mockPush = vi.fn();

vi.mock("@/lib/supabase", () => ({
  supabase: { auth: { signOut: mockSignOut } },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

test("sign out button calls supabase.auth.signOut and redirects", async () => {
  render(<AppHeader user={mockUser} />);
  fireEvent.click(screen.getByText("Sign out"));
  expect(mockSignOut).toHaveBeenCalled();
});

test("shows user initial in avatar", () => {
  render(<AppHeader user={mockUser} />);
  expect(screen.getByText("T")).toBeInTheDocument();
});


// src/store/__tests__/auth.test.ts

import { useAuthStore } from "../index";

test("setUser updates user state", () => {
  const { setUser } = useAuthStore.getState();
  const mockUser = { id: "uuid-123", email: "test@example.com" } as any;
  setUser(mockUser);
  expect(useAuthStore.getState().user).toEqual(mockUser);
});

test("initial user state is null", () => {
  expect(useAuthStore.getState().user).toBeNull();
});
```

---

## Appendix: Key Files

```
apps/web/
  src/
    app/
      (auth)/
        login/
          page.tsx               # Supabase Auth UI login form
          __tests__/page.test.tsx
        signup/
          page.tsx               # Supabase Auth UI signup form
        callback/
          route.ts               # OAuth code → session exchange
      (dashboard)/
        layout.tsx               # Protected layout (server-side session check)
        dashboard/
          page.tsx               # Empty dashboard shell
        settings/
          page.tsx               # User settings stub
      layout.tsx                 # Root layout
      page.tsx                   # Landing page (redirects if authed)
    components/
      AppHeader.tsx              # Top nav with sign-out
      Sidebar.tsx                # Left nav: Rankings, Trends, Exports, Settings
      __tests__/
        AppHeader.test.tsx
    lib/
      supabase.ts                # Browser Supabase client
      supabase-server.ts         # Server Supabase client factory
      utils.ts                   # cn() helper (clsx + tailwind-merge)
    store/
      index.ts                   # Zustand root — AuthState (Phase 1 stub)
      __tests__/
        auth.test.ts
    test/
      setup.ts                   # Vitest setup (jest-dom)
    types/
      supabase.ts                # Generated Supabase Database types
  middleware.ts                  # Session refresh + /dashboard route protection
  vitest.config.ts
  tailwind.config.ts
  components.json                # shadcn/ui config
```

### Environment Variables

```bash
# apps/web/.env.local
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon_key>
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

Never commit `.env.local`. It is gitignored by default in Next.js.

### shadcn/ui Components Used in Phase 1

Install with `npx shadcn@latest add <component>` from `apps/web`:

| Component | Used in |
|-----------|---------|
| `button` | AppHeader sign-out, auth forms |
| `avatar` | AppHeader user avatar |
| `card` | Dashboard placeholder cards |
