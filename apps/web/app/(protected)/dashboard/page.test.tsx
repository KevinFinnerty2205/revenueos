import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DashboardPage from "@/app/(protected)/dashboard/page";

describe("dashboard shell", () => {
  it("renders all required honest empty sections", () => {
    render(<DashboardPage />);

    for (const heading of [
      "Today’s Priorities",
      "Upcoming Meetings",
      "Recent Activity",
      "Tasks",
      "AI Insights",
    ]) {
      expect(screen.getByRole("heading", { name: heading })).toBeVisible();
    }
    expect(screen.getByText(/no ai provider/i)).toBeVisible();
  });
});
