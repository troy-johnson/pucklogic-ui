import Link from "next/link";

const FEATURES = [
  {
    title: "Composite Rankings",
    desc: "Aggregate projections from NHL.com, MoneyPuck, Daily Faceoff, and more into one intelligent rank.",
  },
  {
    title: "Custom Source Weights",
    desc: "Tune how much each projection source influences your final rankings based on your confidence.",
  },
  {
    title: "Live Draft Monitor",
    desc: "Follow picks in real time via the browser extension. Get instant suggestions after every selection.",
  },
  {
    title: "Roster Need Analysis",
    desc: "See positional needs at a glance so you never draft into a position you've already filled.",
  },
  {
    title: "Draft Pass System",
    desc: "Each kit pass unlocks one full draft session — buy what you need, when you need it.",
  },
  {
    title: "Export Draft Sheet",
    desc: "Download your ranked cheat sheet as CSV or PDF before draft day.",
  },
];

const STEPS = [
  {
    num: "01",
    title: "League profile",
    desc: "Enter your league settings — roster slots, scoring format, number of teams.",
  },
  {
    num: "02",
    title: "Weight sources",
    desc: "Slide each projection source's weight to reflect your confidence in it.",
  },
  {
    num: "03",
    title: "Draft",
    desc: "Open the live draft monitor. Get real-time suggestions powered by your kit.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-bg-base text-text-primary">
      {/* Nav */}
      <header className="sticky top-0 z-50 border-b border-border-subtle bg-bg-base/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <span className="text-base font-semibold tracking-tight">
            PuckLogic
          </span>
          <nav className="hidden items-center gap-6 md:flex">
            {["Features", "Pricing", "Sources", "Docs"].map((item) => (
              <a
                key={item}
                href={`#${item.toLowerCase()}`}
                className="text-sm text-text-secondary hover:text-text-primary transition-colors"
              >
                {item}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Link
              href="/login"
              className="rounded px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="pl-btn-primary rounded px-3 py-1.5 text-sm"
            >
              Start free kit
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-4xl px-4 py-24 text-center">
        <div className="mb-4 inline-flex items-center rounded-full border border-accent-blue-dim bg-accent-blue-dim px-3 py-1 text-xs font-medium text-accent-blue">
          Fantasy hockey draft kit
        </div>
        <h1 className="mb-5 text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
          Draft smarter with
          <br />
          <span className="text-accent-blue">AI-ranked projections</span>
        </h1>
        <p className="mx-auto mb-8 max-w-xl text-lg text-text-secondary">
          PuckLogic aggregates projections from every major source, lets you
          tune the weights, and monitors your draft in real time.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/signup"
            className="pl-btn-primary rounded-md px-5 py-2.5 text-sm font-semibold"
          >
            Get started free
          </Link>
          <Link
            href="#features"
            className="pl-btn-secondary rounded-md px-5 py-2.5 text-sm font-semibold"
          >
            See how it works
          </Link>
        </div>
      </section>

      {/* Steps strip */}
      <section id="features" className="border-y border-border-subtle bg-bg-surface py-12">
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-8 px-4 sm:grid-cols-3">
          {STEPS.map(({ num, title, desc }) => (
            <div key={num} className="flex gap-4">
              <span className="mt-0.5 text-2xl font-bold text-accent-blue opacity-60">
                {num}
              </span>
              <div>
                <h3 className="mb-1 font-semibold">{title}</h3>
                <p className="text-sm text-text-secondary">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Features grid */}
      <section className="mx-auto max-w-6xl px-4 py-20">
        <h2 className="mb-10 text-center text-2xl font-bold">
          Everything you need on draft day
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ title, desc }) => (
            <div key={title} className="pl-card rounded-lg p-5">
              <h3 className="mb-2 font-semibold">{title}</h3>
              <p className="text-sm text-text-secondary">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section
        id="pricing"
        className="border-t border-border-subtle bg-bg-surface py-20"
      >
        <div className="mx-auto max-w-3xl px-4 text-center">
          <h2 className="mb-3 text-2xl font-bold">Simple, one-time pricing</h2>
          <p className="mb-10 text-text-secondary">
            Buy draft passes as you need them. No subscription required.
          </p>
          <div className="mx-auto max-w-xs rounded-xl border border-accent-blue bg-bg-elevated p-6 text-center">
            <p className="mb-1 text-sm font-medium text-accent-blue">
              Draft Pass
            </p>
            <p className="mb-4 text-4xl font-bold">$4.99</p>
            <p className="mb-6 text-sm text-text-secondary">
              One full draft session with live monitor and AI suggestions
            </p>
            <Link
              href="/signup"
              className="pl-btn-primary block rounded-md py-2 text-sm font-semibold"
            >
              Buy a pass
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border-subtle px-4 py-8">
        <div className="mx-auto flex max-w-6xl items-center justify-between text-xs text-text-tertiary">
          <span>© 2026 PuckLogic</span>
          <div className="flex gap-4">
            <a href="/privacy" className="hover:text-text-secondary">Privacy</a>
            <a href="/terms" className="hover:text-text-secondary">Terms</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
