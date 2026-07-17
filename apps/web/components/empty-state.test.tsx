import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "@/components/empty-state";

describe("EmptyState", () => {
  it("renders an accessible honest placeholder without a fake action", () => {
    render(
      <EmptyState
        title="No meeting records are available yet"
        description="This build does not store meetings."
      />,
    );

    expect(
      screen.getByRole("heading", {
        name: "No meeting records are available yet",
      }),
    ).toBeVisible();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
