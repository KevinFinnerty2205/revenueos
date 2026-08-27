# ADR 0050: Deterministic in-process PPTX rendering

## Context

Create needs editable PowerPoint output while preserving approved source design.
Running desktop Office or LibreOffice in production expands the execution and sandbox
boundary; rebuilding slides from scratch weakens brand fidelity and layout safety.

## Decision

Use a hardened ZIP/XML preflight and `python-pptx` for deterministic approved-slide
selection and bounded text-placeholder replacement. Do not execute Office,
LibreOffice, links, scripts or embedded objects in production. Strip unselected slide
relationships, notes, comments, custom properties, thumbnails and source metadata.
Use structured in-app review; reserve local headless rendering for development visual
QA only.

## Alternatives

- **Server-side Microsoft Office/LibreOffice:** rejected for the WO-032 security and
  operational boundary.
- **Image/PDF-only export:** rejected because sellers require editable PPTX.
- **Recreate every slide in HTML/canvas:** rejected because it loses approved masters,
  media and brand geometry.

## Consequences

The output remains editable and source-faithful for supported placeholder edits, but
RevenueOS does not promise pixel-perfect browser preview or arbitrary layout repair.
Unsupported packages fail safely and complex canvas editing remains out of scope.
