import type { Company, Contact, Opportunity, Task } from "@revenueos/shared";

export type BusinessEntityName =
  "companies" | "contacts" | "opportunities" | "tasks";

export interface BusinessEntityMap {
  companies: Company;
  contacts: Contact;
  opportunities: Opportunity;
  tasks: Task;
}

export interface EntityOption {
  label: string;
  value: string;
}

export const entityLabels: Record<
  BusinessEntityName,
  { singular: string; plural: string; eyebrow: string; description: string }
> = {
  companies: {
    singular: "company",
    plural: "Companies",
    eyebrow: "Relationships",
    description:
      "Keep the organisations your team works with in one clear view.",
  },
  contacts: {
    singular: "contact",
    plural: "Contacts",
    eyebrow: "People",
    description: "Manage the people connected to your customer relationships.",
  },
  opportunities: {
    singular: "opportunity",
    plural: "Opportunities",
    eyebrow: "Pipeline",
    description: "Track commercial opportunities and their current stage.",
  },
  tasks: {
    singular: "task",
    plural: "Tasks",
    eyebrow: "Follow-through",
    description: "Keep explicit next actions visible and accountable.",
  },
};

export function humanise(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
