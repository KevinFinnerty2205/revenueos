import { PageHeader } from "@/components/page-header";

const dashboardSections = [
  {
    title: "Today’s Priorities",
    description:
      "Priorities will appear here when task and relationship workflows are implemented.",
  },
  {
    title: "Upcoming Meetings",
    description:
      "Deliberate meeting records are available in Meetings; calendar connections are not implemented.",
  },
  {
    title: "Recent Activity",
    description:
      "Meeting audit history is available on each meeting; a combined activity feed is not implemented.",
  },
  {
    title: "Tasks",
    description:
      "Task records are available in Tasks; a dashboard summary is not implemented.",
  },
  {
    title: "AI Insights",
    description:
      "No AI provider or meeting-analysis workflow is connected in this foundation.",
  },
] as const;

export default function DashboardPage() {
  return (
    <>
      <PageHeader
        eyebrow="Development workspace"
        title="A calm place for the work ahead."
        description="Core business and deliberate meeting records are available. Recording, connected conversations and AI capabilities remain unimplemented."
      />
      <section aria-labelledby="dashboard-sections-title">
        <h2 id="dashboard-sections-title" className="sr-only">
          Dashboard sections
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {dashboardSections.map((section, index) => (
            <article
              key={section.title}
              className={
                "rounded-3xl border border-slate-200 bg-white p-6 shadow-sm " +
                (index === 0 ? "sm:col-span-2" : "")
              }
            >
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">
                Empty
              </p>
              <h3 className="mt-3 text-xl font-semibold tracking-tight text-slate-950">
                {section.title}
              </h3>
              <p className="mt-3 text-sm leading-6 text-slate-600">
                {section.description}
              </p>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
