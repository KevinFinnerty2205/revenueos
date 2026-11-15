import {
  expect,
  test,
  type APIRequestContext,
  type BrowserContext,
} from "@playwright/test";
import type {
  ConversationWorkspaceResponse,
  DeliveryPreferenceResponse,
  Meeting,
} from "@revenueos/shared";

const apiBaseUrl = process.env.FULL_STACK_API_URL ?? "http://localhost:8000";

async function createMeetingBackedConversation(
  request: APIRequestContext,
): Promise<Meeting> {
  const response = await request.post(`${apiBaseUrl}/api/v1/meetings`, {
    data: {
      title: `Private-note persistence ${crypto.randomUUID()}`,
      description: "Synthetic full-stack persistence acceptance fixture.",
      meetingDate: new Date(Date.now() + 60 * 60 * 1_000).toISOString(),
      meetingType: "in_person",
      status: "scheduled",
      participants: [],
    },
  });
  expect(response.status()).toBe(201);
  return (await response.json()) as Meeting;
}

async function scrubWorkspaceAndDeleteMeeting(
  request: APIRequestContext,
  meeting: Meeting,
): Promise<void> {
  const workspaceUrl = `${apiBaseUrl}/api/v1/interactions/${meeting.interactionId}/personal-workspace`;
  const workspaceResponse = await request.get(workspaceUrl);
  expect(workspaceResponse.ok()).toBeTruthy();
  const workspace =
    (await workspaceResponse.json()) as ConversationWorkspaceResponse;

  if (workspace.exists) {
    const scrubResponse = await request.put(workspaceUrl, {
      data: {
        expectedLockVersion: workspace.lockVersion,
        liveNotes: null,
        enhancedNotes: null,
        followUpDraft: null,
        followUpReviewed: false,
        generationFingerprint: null,
        importFromBrowser: false,
      },
    });
    expect(scrubResponse.ok()).toBeTruthy();
  }

  const deleteResponse = await request.delete(
    `${apiBaseUrl}/api/v1/meetings/${meeting.id}`,
  );
  expect(deleteResponse.status()).toBe(204);
}

test("briefing preferences survive a new browser context through the real API and PostgreSQL", async ({
  browser,
  request,
}) => {
  const originalResponse = await request.get(
    `${apiBaseUrl}/api/v1/daily/preferences`,
  );
  expect(originalResponse.ok()).toBeTruthy();
  const original =
    (await originalResponse.json()) as DeliveryPreferenceResponse;
  const changedMinutes = original.preMeetingMinutes === 75 ? 76 : 75;
  let persisted: DeliveryPreferenceResponse | null = null;

  try {
    const firstContext = await browser.newContext();
    const firstPage = await firstContext.newPage();
    await firstPage.goto("/settings");
    const firstLeadTime = firstPage.getByLabel("Briefing lead time (minutes)");
    await expect(firstLeadTime).toHaveValue(
      String(original.preMeetingMinutes),
      {
        timeout: 20_000,
      },
    );
    await firstLeadTime.fill(String(changedMinutes));
    await firstLeadTime.press("Tab");
    const saveResponsePromise = firstPage.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === "/api/v1/daily/preferences" &&
        response.request().method() === "PUT",
    );
    await firstPage.getByRole("button", { name: "Save preferences" }).click();
    const saveResponse = await saveResponsePromise;
    expect(saveResponse.ok()).toBeTruthy();
    const saved = (await saveResponse.json()) as DeliveryPreferenceResponse;
    expect(saved.preMeetingMinutes).toBe(changedMinutes);
    await expect(
      firstPage.getByText(/Preferences saved privately/i),
    ).toBeVisible();
    await firstContext.close();

    await expect
      .poll(
        async () => {
          const persistedResponse = await request.get(
            `${apiBaseUrl}/api/v1/daily/preferences`,
          );
          if (!persistedResponse.ok()) return null;
          const candidate =
            (await persistedResponse.json()) as DeliveryPreferenceResponse;
          return candidate.preMeetingMinutes;
        },
        {
          message: "the API to expose the committed preference update",
          timeout: 5_000,
        },
      )
      .toBe(changedMinutes);
    const persistedResponse = await request.get(
      `${apiBaseUrl}/api/v1/daily/preferences`,
    );
    expect(persistedResponse.ok()).toBeTruthy();
    persisted = (await persistedResponse.json()) as DeliveryPreferenceResponse;
    expect(persisted.lockVersion).toBe(original.lockVersion + 1);

    const secondContext = await browser.newContext();
    const secondPage = await secondContext.newPage();
    await secondPage.goto("/settings");
    await expect(
      secondPage.getByLabel("Briefing lead time (minutes)"),
    ).toHaveValue(String(changedMinutes), { timeout: 20_000 });
    await secondContext.close();
  } finally {
    if (persisted) {
      const restoreResponse = await request.put(
        `${apiBaseUrl}/api/v1/daily/preferences`,
        {
          data: {
            expectedLockVersion: persisted.lockVersion,
            timezone: original.timezone,
            morningDigestEnabled: original.morningDigestEnabled,
            morningDigestTime: original.morningDigestTime,
            preMeetingEnabled: original.preMeetingEnabled,
            preMeetingMinutes: original.preMeetingMinutes,
            importFromBrowser: false,
          },
        },
      );
      expect(restoreResponse.ok()).toBeTruthy();
    }
  }
});

test("private notes survive reload while a stale browser keeps its local conflict text", async ({
  browser,
  request,
}) => {
  let meeting: Meeting | null = null;
  let firstContext: BrowserContext | null = null;
  let secondContext: BrowserContext | null = null;

  try {
    meeting = await createMeetingBackedConversation(request);
    const workspacePath = `/api/v1/interactions/${meeting.interactionId}/personal-workspace`;
    const workspaceUrl = `${apiBaseUrl}${workspacePath}`;
    const initialResponse = await request.get(workspaceUrl);
    expect(initialResponse.ok()).toBeTruthy();
    const initial =
      (await initialResponse.json()) as ConversationWorkspaceResponse;
    expect(initial).toMatchObject({ exists: false, lockVersion: 0 });

    [firstContext, secondContext] = await Promise.all([
      browser.newContext(),
      browser.newContext(),
    ]);
    const firstPage = await firstContext.newPage();
    const secondPage = await secondContext.newPage();
    const conversationUrl = `/conversations/${meeting.interactionId}?view=capture`;
    await Promise.all([
      firstPage.goto(conversationUrl),
      secondPage.goto(conversationUrl),
    ]);

    const firstNotes = firstPage.getByLabel("Private live notes");
    const secondNotes = secondPage.getByLabel("Private live notes");
    await expect(firstNotes).toBeEditable({ timeout: 20_000 });
    await expect(secondNotes).toBeEditable({ timeout: 20_000 });
    await expect(firstNotes).toHaveValue("");
    await expect(secondNotes).toHaveValue("");

    const committedText = "Committed note from the first browser session.";
    const staleLocalText =
      "Unsaved local note from the stale second browser session.";
    await firstNotes.fill(committedText);
    await secondNotes.fill(staleLocalText);

    const firstSaveResponsePromise = firstPage.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === workspacePath &&
        response.request().method() === "PUT",
    );
    await firstPage
      .getByRole("button", { name: "Save private notes", exact: true })
      .click();
    const firstSaveResponse = await firstSaveResponsePromise;
    expect(firstSaveResponse.ok()).toBeTruthy();
    const saved =
      (await firstSaveResponse.json()) as ConversationWorkspaceResponse;
    expect(saved).toMatchObject({
      exists: true,
      liveNotes: committedText,
      lockVersion: 1,
    });
    await expect(
      firstPage.getByText("Private notes saved.", { exact: true }),
    ).toBeVisible();

    const staleSaveResponsePromise = secondPage.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === workspacePath &&
        response.request().method() === "PUT",
    );
    await secondPage
      .getByRole("button", { name: "Save private notes", exact: true })
      .click();
    const staleSaveResponse = await staleSaveResponsePromise;
    expect(staleSaveResponse.status()).toBe(409);
    expect(await staleSaveResponse.json()).toMatchObject({
      code: "conversation_workspace_conflict",
    });
    await expect(secondNotes).toHaveValue(staleLocalText);
    await expect(
      secondPage
        .getByRole("status")
        .filter({ hasText: /changed in another session/i }),
    ).toBeVisible();

    await firstPage.reload();
    await expect(firstPage.getByLabel("Private live notes")).toHaveValue(
      committedText,
      { timeout: 20_000 },
    );

    const persistedResponse = await request.get(workspaceUrl);
    expect(persistedResponse.ok()).toBeTruthy();
    const persisted =
      (await persistedResponse.json()) as ConversationWorkspaceResponse;
    expect(persisted).toMatchObject({
      exists: true,
      liveNotes: committedText,
      lockVersion: saved.lockVersion,
    });
  } finally {
    await firstContext?.close();
    await secondContext?.close();
    if (meeting) await scrubWorkspaceAndDeleteMeeting(request, meeting);
  }
});
