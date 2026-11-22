import { act, fireEvent, render, screen } from "@testing-library/react";
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
    <>
      <p role="status">
        {organisation.status}:{organisation.organisationId ?? "none"}:
        {organisation.userId ?? "none"}
      </p>
      <button type="button" onClick={organisation.reload}>
        Retry identity
      </button>
    </>
  );
}

describe("VerifiedOrganisationProvider", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("derives the trusted organisation from the authenticated /me response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        organisation: { id: "organisation-internal" },
        user: { id: "user-internal" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <VerifiedOrganisationProvider identityKey="external-session-one">
        <OrganisationProbe />
      </VerifiedOrganisationProvider>,
    );

    expect(screen.getByRole("status")).toHaveTextContent("loading:none:none");
    expect(
      await screen.findByText("available:organisation-internal:user-internal"),
    ).toBeVisible();
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/api/v1/me");
  });

  it.each([
    ["missing organisation", {}],
    [
      "malformed organisation",
      { organisation: { id: 42 }, user: { id: "user-internal" } },
    ],
    ["missing user", { organisation: { id: "organisation-internal" } }],
    [
      "malformed user",
      { organisation: { id: "organisation-internal" }, user: { id: 42 } },
    ],
  ])("fails closed for a %s response", async (_case, payload) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(payload)));

    render(
      <VerifiedOrganisationProvider identityKey="external-session-one">
        <OrganisationProbe />
      </VerifiedOrganisationProvider>,
    );

    expect(await screen.findByText("unavailable:none:none")).toBeVisible();
  });

  it("hides the previous verified organisation synchronously when identity changes", async () => {
    const secondResponse = deferred<Response>();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          organisation: { id: "organisation-one" },
          user: { id: "user-one" },
        }),
      )
      .mockReturnValueOnce(secondResponse.promise);
    vi.stubGlobal("fetch", fetchMock);

    const view = render(
      <VerifiedOrganisationProvider identityKey="external-session-one">
        <OrganisationProbe />
      </VerifiedOrganisationProvider>,
    );
    expect(
      await screen.findByText("available:organisation-one:user-one"),
    ).toBeVisible();

    view.rerender(
      <VerifiedOrganisationProvider identityKey="external-session-two">
        <OrganisationProbe />
      </VerifiedOrganisationProvider>,
    );

    expect(screen.getByRole("status")).toHaveTextContent("loading:none:none");
    expect(screen.queryByText(/organisation-one/u)).not.toBeInTheDocument();

    await act(async () => {
      secondResponse.resolve(
        jsonResponse({
          organisation: { id: "organisation-two" },
          user: { id: "user-two" },
        }),
      );
      await secondResponse.promise;
    });
    expect(
      await screen.findByText("available:organisation-two:user-two"),
    ).toBeVisible();
  });

  it("retries a failed identity verification without a page refresh", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("Identity temporarily unavailable"))
      .mockResolvedValueOnce(
        jsonResponse({
          organisation: { id: "organisation-internal" },
          user: { id: "user-internal" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <VerifiedOrganisationProvider identityKey="external-session-one:user-one">
        <OrganisationProbe />
      </VerifiedOrganisationProvider>,
    );

    expect(await screen.findByText("unavailable:none:none")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Retry identity" }));
    expect(screen.getByRole("status")).toHaveTextContent("loading:none:none");
    expect(
      await screen.findByText("available:organisation-internal:user-internal"),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
