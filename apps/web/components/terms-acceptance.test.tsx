import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TermsAcceptance } from "@/components/terms-acceptance";

const pendingStatus = {
  terms: {
    status: "draft",
    version: "owner-review-draft-v1",
    fingerprint:
      "sha256:9425fe5c0d056e7669ee1fc8e3f977a5cd7d639ce775d36926bb89de54330652",
    effectiveDate: null,
    href: "/terms",
  },
  privacyNotice: {
    status: "draft",
    version: "owner-review-draft-v1",
    fingerprint:
      "sha256:31cbce440f61c97f033c8cca75b252f56a21832cc8b8585387e553327f681c22",
    effectiveDate: null,
    href: "/privacy",
  },
  accepted: false,
  acceptanceAvailable: true,
  canAccept: true,
  evidence: null,
  message:
    "An organisation administrator must accept the current Terms before continuing.",
} as const;

describe("TermsAcceptance", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("requires an unchecked authority control and moves focus after explicit acceptance", async () => {
    const fetch = vi.fn((_: RequestInfo | URL, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "GET") {
        return Promise.resolve(
          new Response(JSON.stringify(pendingStatus), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            ...pendingStatus,
            accepted: true,
            evidence: {
              id: "00000000-0000-4000-8000-000000000004",
              acceptedByUserId: "00000000-0000-4000-8000-000000000001",
              termsVersion: pendingStatus.terms.version,
              termsFingerprint: pendingStatus.terms.fingerprint,
              termsEffectiveDate: null,
              acceptedAt: "2026-09-10T00:00:00Z",
              acceptanceSource: "trial_onboarding",
              privacyNoticeVersion: pendingStatus.privacyNotice.version,
              privacyNoticeFingerprint: pendingStatus.privacyNotice.fingerprint,
              privacyNoticeEffectiveDate: null,
              privacyNoticePresentedAt: "2026-09-10T00:00:00Z",
            },
            message: "Your organisation has accepted the current Terms.",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    });
    vi.stubGlobal("fetch", fetch);

    render(
      <TermsAcceptance source="trial_onboarding">
        <p>Trial onboarding unlocked</p>
      </TermsAcceptance>,
    );

    const checkbox = await screen.findByRole("checkbox", {
      name: /I confirm that I am authorised/i,
    });
    const button = screen.getByRole("button", {
      name: "Accept Terms for organisation",
    });
    expect(checkbox).not.toBeChecked();
    expect(button).toBeDisabled();
    expect(
      screen.getByRole("link", { name: "Oryntela Terms & Conditions" }),
    ).toHaveAttribute("href", "/terms");
    expect(
      screen.getByRole("link", { name: "Privacy Policy" }),
    ).toHaveAttribute("href", "/privacy");
    expect(
      screen.getByText(/not a separate contract acceptance/i),
    ).toBeVisible();

    checkbox.focus();
    expect(checkbox).toHaveFocus();
    fireEvent.click(checkbox);
    expect(button).toBeEnabled();
    fireEvent.click(button);

    const confirmation = await screen.findByRole("status");
    expect(confirmation).toHaveTextContent(
      "Current Terms accepted for this organisation",
    );
    expect(confirmation).toHaveFocus();
    expect(screen.getByText("Trial onboarding unlocked")).toBeVisible();
    expect(JSON.parse(String(fetch.mock.calls.at(-1)?.[1]?.body))).toEqual({
      authorityAndTermsAccepted: true,
      source: "trial_onboarding",
    });
  });

  it("tells an ordinary member to ask an administrator without showing an acceptance control", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              ...pendingStatus,
              canAccept: false,
              message:
                "Ask an organisation administrator to accept the current Terms before continuing.",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        ),
      ),
    );

    render(<TermsAcceptance source="trial_onboarding" />);

    expect(
      await screen.findByText(/Ask an organisation administrator/i),
    ).toBeVisible();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Accept Terms/i }),
    ).not.toBeInTheDocument();
  });

  it("offers an accessible retry and never follows legal links supplied by an API response", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(
        new Error("Terms status is temporarily unavailable."),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ...pendingStatus,
            terms: {
              ...pendingStatus.terms,
              href: "https://unsafe.example/terms",
            },
            privacyNotice: {
              ...pendingStatus.privacyNotice,
              href: "javascript:alert('unsafe')",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetch);

    render(<TermsAcceptance source="trial_onboarding" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /could not reach the service/i,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Retry loading Terms" }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Accept the current Terms to continue",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Oryntela Terms & Conditions" }),
    ).toHaveAttribute("href", "/terms");
    expect(
      screen.getByRole("link", { name: "Privacy Policy" }),
    ).toHaveAttribute("href", "/privacy");
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
