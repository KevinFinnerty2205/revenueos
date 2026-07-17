import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "@/components/empty-state";

describe("EmptyState", () => {
  it("renders an accessible honest placeholder without a fake action", () => {
    render(
      <EmptyState
        title="Company records are not available yet"
        description="Sprint 1 does not store customer records."
      />,
    );

    expect(
      screen.getByRole("heading", {
        name: "Company records are not available yet",
      }),
    ).toBeVisible();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
