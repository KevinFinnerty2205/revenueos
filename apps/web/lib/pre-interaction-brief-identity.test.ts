import { describe, expect, it } from "vitest";
import {
  assertPreInteractionBriefIdentity,
  PRE_INTERACTION_BRIEF_IDENTITY_ERROR,
} from "@/lib/pre-interaction-brief-identity";

describe("assertPreInteractionBriefIdentity", () => {
  it("accepts empty and completed responses for the expected interaction", () => {
    expect(() =>
      assertPreInteractionBriefIdentity(
        { interactionId: "interaction-1", brief: null },
        "interaction-1",
      ),
    ).not.toThrow();
    expect(() =>
      assertPreInteractionBriefIdentity(
        {
          interactionId: "interaction-1",
          brief: { interactionId: "interaction-1" },
        },
        "interaction-1",
      ),
    ).not.toThrow();
  });

  it.each([
    { interactionId: "interaction-2", brief: null },
    {
      interactionId: "interaction-1",
      brief: { interactionId: "interaction-2" },
    },
    { interactionId: "interaction-1" },
  ])("rejects a response without exact identity", (response) => {
    expect(() =>
      assertPreInteractionBriefIdentity(response, "interaction-1"),
    ).toThrow(PRE_INTERACTION_BRIEF_IDENTITY_ERROR);
  });
});
