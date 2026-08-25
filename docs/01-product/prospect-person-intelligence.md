# Prospect Person Intelligence implementation guide

## Current implementation

WO-027 extends a researched Prospect company with a bounded **People worth understanding** workflow. A seller starts from one company research target, requests discovery, chooses a person and runs source-backed professional research. There is no global people search.

The brief covers current public role, professional background and activity, why the person may matter, cautious conversation context, buying-committee hypotheses and business contact points. Every material finding cites a permitted public source or the deterministic provider. `verified`, `provider_supplied`, `inferred` and `unknown` remain distinct.

A Prospect Person is research context, not a Contact or stakeholder. **Add to Sales as Contact** is a separate, confirmed action. It creates or links one canonical Contact after conservative duplicate review; it does not create an Opportunity, confirm a stakeholder, change Methodology, write Evidence or Revenue Brain, or start outreach.

## Safety boundary

The implementation excludes personal emails and mobiles, private-social data, sensitive traits, family or private-life interests, personality profiling, photos, facial processing, bulk discovery/export and background monitoring. Public availability and passive verification do not establish permission to contact.

The production provider remains unconfigured. Local and automated flows use synthetic identities from the deterministic mock provider; models cannot invent real identities. WO-028 owns ICP/territory intelligence and WO-029 owns any future reviewed outreach.
