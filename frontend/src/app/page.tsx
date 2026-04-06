import Link from "next/link";

const featureCards = [
  {
    title: "See what is about to expire",
    body: "NeverMiss surfaces hidden renewals, vouchers, warranties, and memberships from the inbox you already use.",
  },
  {
    title: "Keep the useful parts, skip the noise",
    body: "You get the sender, the date, and the deadline context you need without reading through old email threads.",
  },
  {
    title: "Move fast when something matters",
    body: "Dismiss handled items, export the important ones to Google Calendar, and keep your queue clean.",
  },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.22),_transparent_26%),radial-gradient(circle_at_bottom_right,_rgba(249,115,22,0.16),_transparent_28%),linear-gradient(180deg,_#fff7ed_0%,_#fffbeb_35%,_#f8fafc_100%)] px-6 py-8 md:px-10">
      <div className="mx-auto max-w-7xl">
        <header className="flex items-center justify-between rounded-full border border-white/70 bg-white/75 px-6 py-4 shadow-[0_18px_60px_-36px_rgba(15,23,42,0.4)] backdrop-blur">
          <Link href="/" className="text-lg font-semibold tracking-tight text-slate-950">
            NeverMiss
          </Link>
          <nav className="flex items-center gap-3">
            <Link
              href="/pricing"
              className="rounded-full px-4 py-2 text-sm font-medium text-slate-600 transition hover:text-slate-950"
            >
              Pricing
            </Link>
            <Link
              href="/login"
              className="rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800"
            >
              Connect Gmail
            </Link>
          </nav>
        </header>

        <section className="grid gap-10 px-2 py-16 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
          <div className="space-y-8">
            <div className="inline-flex rounded-full border border-amber-200 bg-amber-50 px-4 py-2 text-xs font-semibold uppercase tracking-[0.35em] text-amber-700">
              Inbox intelligence for real life
            </div>
            <div className="space-y-5">
              <h1 className="max-w-4xl text-5xl font-semibold tracking-tight text-slate-950 sm:text-6xl">
                Stop losing money and missing deadlines hidden in your email.
              </h1>
              <p className="max-w-2xl text-lg leading-8 text-slate-600">
                NeverMiss scans Gmail for subscriptions, renewals, vouchers, warranties, and important cutoff dates so you can act before something slips past you.
              </p>
            </div>

            <div className="flex flex-col gap-4 sm:flex-row">
              <Link
                href="/login"
                className="rounded-[20px] bg-slate-950 px-6 py-4 text-center text-sm font-semibold text-white transition hover:bg-slate-800"
              >
                Start with Google
              </Link>
              <Link
                href="/pricing"
                className="rounded-[20px] border border-slate-200 bg-white px-6 py-4 text-center text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-950"
              >
                See pricing
              </Link>
            </div>

            <div className="rounded-[28px] border border-emerald-200 bg-emerald-50/80 p-6 shadow-[0_20px_50px_-38px_rgba(5,150,105,0.5)]">
              <p className="text-sm font-medium text-emerald-900">
                Your emails are processed, not stored. We see your inbox for seconds, not forever.
              </p>
            </div>
          </div>

          <div className="relative">
            <div className="absolute -left-6 top-10 h-40 w-40 rounded-full bg-amber-300/30 blur-3xl" />
            <div className="absolute -right-4 bottom-6 h-48 w-48 rounded-full bg-orange-400/20 blur-3xl" />
            <div className="relative overflow-hidden rounded-[36px] border border-white/60 bg-slate-950 p-8 text-white shadow-[0_36px_100px_-42px_rgba(15,23,42,0.9)]">
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-300">
                    Live queue
                  </span>
                  <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-200">
                    12 items found
                  </span>
                </div>

                <div className="space-y-4">
                  <div className="rounded-[26px] bg-white/10 p-5">
                    <p className="text-xs uppercase tracking-[0.3em] text-rose-200">Critical</p>
                    <h2 className="mt-2 text-2xl font-semibold">Travel insurance renewal</h2>
                    <p className="mt-2 text-sm text-slate-300">Found in email from Allianz on Apr 2</p>
                  </div>
                  <div className="rounded-[26px] bg-white/5 p-5">
                    <p className="text-xs uppercase tracking-[0.3em] text-amber-200">Soon</p>
                    <h2 className="mt-2 text-2xl font-semibold">Canva Pro annual plan</h2>
                    <p className="mt-2 text-sm text-slate-300">Renews in 24 days</p>
                  </div>
                  <div className="rounded-[26px] bg-white/5 p-5">
                    <p className="text-xs uppercase tracking-[0.3em] text-emerald-200">On radar</p>
                    <h2 className="mt-2 text-2xl font-semibold">Domain transfer lock</h2>
                    <p className="mt-2 text-sm text-slate-300">Expires in 147 days</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-5 pb-12 md:grid-cols-3">
          {featureCards.map((card) => (
            <article
              key={card.title}
              className="rounded-[28px] border border-white/60 bg-white/75 p-6 shadow-[0_24px_60px_-42px_rgba(15,23,42,0.45)] backdrop-blur"
            >
              <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
                {card.title}
              </h2>
              <p className="mt-3 text-sm leading-7 text-slate-600">{card.body}</p>
            </article>
          ))}
        </section>
      </div>
    </main>
  );
}
