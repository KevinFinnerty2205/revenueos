# Visual provenance rules

## Required dimensions

Every visual has a source ownership independent of AI origin:

- `customer_created` — supplied or created by the customer;
- `salesperson_created` — prepared by the seller;
- `jointly_created` — produced collaboratively;
- `unknown_origin` — ownership cannot be established.

Provider candidates always use origin `ai_inferred`. Review changes validation from `unreviewed` to `verified` or `rejected`; it does not change origin or source ownership.

## Support classification

- `direct` means the visual directly depicts customer-created or jointly created material.
- `observed` is mandatory for site-photo interpretation and must be presented as an observation requiring validation.
- `context` covers seller-created and unknown-origin contextual material.

## Downstream eligibility

Seller-created material cannot create customer requests, decisions, action items, objections, commercial intent, budget, timeline or procurement signals. Business cards never update Interaction Intelligence or Revenue Brain. Site photos can contribute only technical constraints, implementation requirements, risks or other observed context. All other eligible claims require explicit user acceptance.

Deletion marks accepted and source Evidence deleted and removes candidate rows. Current Opportunity and Revenue Brain reads reject any snapshot whose source Evidence is no longer verified and available.

## Conflict handling

Visual candidates start `not_assessed`. The schema supports `conflicting` without resolving conflict automatically. A later work order may compare evidence across sources; WO-014 does not silently arbitrate disagreement or calculate truth scores.
