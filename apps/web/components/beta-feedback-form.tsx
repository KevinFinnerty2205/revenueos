"use client";

import { apiRequest } from "@/lib/api";
import { usePathname } from "next/navigation";
import { FormEvent, useState } from "react";

const categories = [
  ["bug", "Something is broken"],
  ["confusing", "Something is confusing"],
  ["inaccurate_intelligence", "Intelligence looks inaccurate"],
  ["missing_feature", "A capability is missing"],
  ["other", "Other feedback"],
] as const;

export function BetaFeedbackForm() {
  const pathname = usePathname();
  const [category, setCategory] =
    useState<(typeof categories)[number][0]>("bug");
  const [rating, setRating] = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setStatus(null);
    try {
      await apiRequest("/api/v1/beta/feedback", {
        method: "POST",
        body: JSON.stringify({
          category,
          rating: rating ? Number(rating) : null,
          message,
          currentRoute: pathname,
        }),
      });
      setMessage("");
      setRating("");
      setStatus("Thanks — your feedback was sent to the private beta team.");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Feedback could not be submitted.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      className="form-card space-y-6"
      onSubmit={(event) => void submit(event)}
    >
      <div>
        <label
          htmlFor="feedback-category"
          className="block text-sm font-bold text-slate-800"
        >
          Category
        </label>
        <select
          id="feedback-category"
          className="form-control mt-2 w-full"
          value={category}
          onChange={(event) =>
            setCategory(event.target.value as typeof category)
          }
        >
          {categories.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label
          htmlFor="feedback-rating"
          className="block text-sm font-bold text-slate-800"
        >
          Rating <span className="font-normal text-slate-500">(optional)</span>
        </label>
        <select
          id="feedback-rating"
          className="form-control mt-2 w-full"
          value={rating}
          onChange={(event) => setRating(event.target.value)}
        >
          <option value="">No rating</option>
          {[1, 2, 3, 4, 5].map((value) => (
            <option key={value} value={value}>
              {value} of 5
            </option>
          ))}
        </select>
      </div>
      <div>
        <label
          htmlFor="feedback-message"
          className="block text-sm font-bold text-slate-800"
        >
          Short message
        </label>
        <textarea
          id="feedback-message"
          className="form-control mt-2 min-h-36 w-full py-3"
          required
          minLength={1}
          maxLength={2000}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
        />
        <p className="mt-2 text-xs text-slate-500">
          Do not paste transcripts, generated content, secrets or
          customer-sensitive material.
        </p>
      </div>
      <button className="primary-button" disabled={saving}>
        {saving ? "Sending feedback…" : "Send feedback"}
      </button>
      {status ? (
        <p
          role="status"
          aria-live="polite"
          className="rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-950"
        >
          {status}
        </p>
      ) : null}
      {error ? (
        <p
          role="alert"
          aria-live="assertive"
          className="rounded-2xl bg-rose-50 p-4 text-sm text-rose-900"
        >
          {error}
        </p>
      ) : null}
    </form>
  );
}
