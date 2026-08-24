# Core empty, loading and error-state guide

- **Status:** WO-025A review baseline
- **Purpose:** tell the seller what remains safe and what to do next

## Rules

- Loading names the work being loaded and does not imply progress that is not known.
- An empty state explains the first useful action; it does not advertise unavailable
  modules.
- A partial failure keeps successful Home, Opportunity or Interaction sections
  usable.
- An error says what failed and provides retry, Search, Home or administrator
  guidance as appropriate.
- Feature-disabled and feature-check-failed states are distinct. Repeated gates use
  unique accessible headings rather than duplicate page-level headings.
- Processing never promises a completion time and preserves the current review path.

## Core examples

| Surface     | Empty or failure recovery                                             |
| ----------- | --------------------------------------------------------------------- |
| Home        | Add/open an Opportunity or next Interaction; calm caught-up state     |
| Search      | Shorten or correct the account/deal/interaction name                  |
| Opportunity | Deal metadata remains; expand meeting administration only when needed |
| Interaction | Return to the list on load failure; capture choices stay deliberate   |
| Actions     | Prepare suggestions only when reviewed evidence exists                |
| Methodology | Explain not configured/not generated/needs refresh without a score    |
| Settings    | Return Home; members are told who owns organisation controls          |
