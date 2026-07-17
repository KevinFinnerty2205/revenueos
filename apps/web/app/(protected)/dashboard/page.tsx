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
      "Calendar and meeting connections are not available in Sprint 1.",
  },
  {
    title: "Recent Activity",
    description:
      "Activity will appear after the product begins storing customer interactions.",
  },
  {
    title: "Tasks",
    description: "Task creation and tracking are planned for a later sprint.",
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
        description="The application shell is ready. Product data and connected capabilities will appear only as later sprints implement them."
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
