# Forecast deal-review UX

Each eligible Opportunity is a responsive card containing current amount, stage,
owner, expected close date, seller category and historical coverage. The owner can
choose one of four plain-language categories and save one deal at a time. Saving is
an explicit action and confirms that a new revision was created.

A **Needs review** badge lists which canonical facts changed after the last review.
Non-owners see the category but an owner-only explanation replaces the save action.
Past periods disable editing. Unreviewed, unvalued and insufficient-history records
stay visible rather than silently falling out of the screen.

The interaction does not edit Opportunity truth. Sellers use the Opportunity record
to correct amount, currency, close date, Pipeline, stage or status.
