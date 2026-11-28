import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useRecordingNavigationGuard } from "@/lib/use-recording-navigation-guard";

function clickLink(
  path: string,
  { target, ...mouse }: MouseEventInit & { target?: string } = {},
) {
  const link = document.createElement("a");
  const label = document.createElement("span");
  link.href = path;
  if (target) link.target = target;
  link.appendChild(label);
  document.body.appendChild(link);
  let blocked = true;
  link.addEventListener("click", (event) => {
    blocked = event.defaultPrevented;
    event.preventDefault();
  });
  const event = new MouseEvent("click", {
    bubbles: true,
    cancelable: true,
    ...mouse,
  });
  label.dispatchEvent(event);
  link.remove();
  return blocked;
}

describe("recording navigation guard", () => {
  afterEach(() => vi.restoreAllMocks());

  it("protects same-tab workspace links and page exits until local audio settles", () => {
    const notice = vi.spyOn(window, "alert").mockImplementation(() => {});
    const { rerender, unmount } = renderHook(
      (blocked) => useRecordingNavigationGuard(blocked),
      { initialProps: true },
    );
    expect(clickLink("/conversations")).toBe(true);
    expect(notice).toHaveBeenCalledWith(
      expect.stringMatching(/finish recording and uploading/i),
    );
    expect(
      window.dispatchEvent(new Event("beforeunload", { cancelable: true })),
    ).toBe(false);

    expect(clickLink("#companion-controls")).toBe(false);
    expect(clickLink("/conversations", { target: "_blank" })).toBe(false);
    expect(clickLink("/conversations", { metaKey: true })).toBe(false);

    rerender(false);
    expect(clickLink("/conversations")).toBe(false);
    expect(
      window.dispatchEvent(new Event("beforeunload", { cancelable: true })),
    ).toBe(true);

    rerender(true);
    unmount();
    expect(clickLink("/conversations")).toBe(false);
    expect(notice).toHaveBeenCalledTimes(1);
  });
});
