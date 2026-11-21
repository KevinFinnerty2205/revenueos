import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  useVerifiedOrganisation,
  VerifiedOrganisationProvider,
} from "@/components/verified-organisation-context";

function jsonResponse(body: object): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function OrganisationProbe() {
  const organisation = useVerifiedOrganisation();
  return (
    <p role="status">
      {organisation.status}:{organisation.organisationId ?? "none"}
    </p>
  );
}

describe("VerifiedOrganisationProvider", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("derives the trusted organisation from the authenticated /me response", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ organisation: { id: "organisation-internal" } }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <VerifiedOrganisationProvider identityKey="external-session-one">
        <OrganisationProbe />
      </VerifiedOrganisationProvider>,
    );

    expect(screen.getByRole("status")).toHaveTextContent("loading:none");
    expect(
      await screen.findByText("available:organisation-internal"),
    ).toBeVisible();
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/api/v1/me");
  });

  it.each([
    ["missing organisation", {}],
    ["malformed organisation", { organisation: { id: 42 } }],
  ])("fails closed for a %s response", async (_case, payload) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(payload)));

    render(
      <VerifiedOrganisationProvider identityKey="external-session-one">
        <OrganisationProbe />
      </VerifiedOrganisationProvider>,
    );

    expect(await screen.findByText("unavailable:none")).toBeVisible();
  });

  it("hides the previous verified organisation synchronously when identity changes", async () => {
    const secondResponse = deferred<Response>();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ organisation: { id: "organisation-one" } }),
      )
      .mockReturnValueOnce(secondResponse.promise);
    vi.stubGlobal("fetch", fetchMock);

    const view = render(
      <VerifiedOrganisationProvider identityKey="external-session-one">
        <OrganisationProbe />
      </VerifiedOrganisationProvider>,
    );
    expect(await screen.findByText("available:organisation-one")).toBeVisible();

    view.rerender(
      <VerifiedOrganisationProvider identityKey="external-session-two">
        <OrganisationProbe />
      </VerifiedOrganisationProvider>,
    );

    expect(screen.getByRole("status")).toHaveTextContent("loading:none");
    expect(screen.queryByText(/organisation-one/u)).not.toBeInTheDocument();

    await act(async () => {
      secondResponse.resolve(
        jsonResponse({ organisation: { id: "organisation-two" } }),
      );
      await secondResponse.promise;
    });
    expect(await screen.findByText("available:organisation-two")).toBeVisible();
  });
});
