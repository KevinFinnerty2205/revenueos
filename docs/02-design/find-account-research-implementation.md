# Find and Account Research UX implementation

**Status:** Current WO-026 design

Entitled desktop workspaces gain one restrained Prospect navigation group with one
destination: **Find**. Mobile navigation remains unchanged to avoid crowding; Find
is still responsive when reached by a link or direct navigation.

The Find page opens with “Which company are you looking for?” and a labelled search
input. Results are bounded candidate cards with name, domain, location and industry.
The seller must choose a card; ambiguous names are never silently resolved. Empty,
unavailable and no-result states retain one obvious next action. Recently researched
targets show ready, partial, in-progress, failed and added-to-sales state without
retaining raw search history.

The brief presents company identity, progress, primary actions, overview, why this
may matter, recent developments, more research and sources. User-facing copy never
mentions providers, leases, workers or queues. A polite live status announces
progress while the client polls persisted state. Polling stops on a terminal state;
page reads do not re-run research.

Refresh is visible but secondary. Add to Sales is the primary action and opens an
explicit confirmation explaining whether RevenueOS will attach an exact-domain
Company or create one. The seller can cancel without mutation. After promotion,
the action links to the Company.

Partial results keep supported findings and explain that more information may not
be available. A failed initial run offers an actionable retry. A failed refresh
shows the prior successful brief. Advanced run history and source metadata are
disclosed below the core answer rather than becoming the main interface.

Accessibility uses semantic headings, labelled search, keyboard-native buttons and
links, live status text, focus-visible controls and text labels for trust state.
Trust never depends on colour alone.
