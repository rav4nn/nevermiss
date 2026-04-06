export default function DashboardLoading() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.18),_transparent_30%),linear-gradient(180deg,_#fffaf2_0%,_#f8fafc_45%,_#eef2ff_100%)] px-6 py-10 md:px-10">
      <div className="mx-auto max-w-7xl animate-pulse space-y-6">
        <div className="h-16 rounded-[32px] bg-white/70" />
        <div className="h-48 rounded-[32px] bg-slate-950/90" />
        <div className="grid gap-5">
          <div className="h-56 rounded-[28px] bg-white/80" />
          <div className="h-56 rounded-[28px] bg-white/80" />
          <div className="h-56 rounded-[28px] bg-white/80" />
        </div>
      </div>
    </main>
  );
}
