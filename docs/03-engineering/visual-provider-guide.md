# Visual provider guide

## Adapter boundary

`VisualAnalysisProvider` receives one sanitised bounded image plus visual type, source ownership and optional context label. It returns a strict `VisualAnalysisResult` with a completed/refused/incomplete finish status and at most 100 typed candidates. Unknown fields, invalid categories, out-of-bounds regions and malformed responses fail validation.

The deterministic `mock` provider is the zero-network local/CI default. It deliberately produces no candidates for seller-created slides/deck pages, contact details only for business cards, and low-confidence observed technical constraints for site photos.

The optional OpenAI Responses adapter is server-side, uses `store=false`, zero SDK retries, a bounded timeout and a strict JSON schema. It sends no storage credentials. Deployment configuration must explicitly enable the provider and supply the normal OpenAI API key/model settings.

## Prompt-injection boundary

Text visible inside an image and the user’s context label are untrusted evidence, never instructions. The system prompt states that image text must not alter policy or output shape. Service-level rules run after provider validation, so a provider cannot bypass seller-material, business-card or site-photo restrictions.

## Logging

Execution logs and beta events contain metadata only: tenant context, visual ID, byte count, visual type, ownership, attempt/result counts and safe failure codes. Image bytes, OCR snippets, context labels, statements, signed URLs and full provider payloads are prohibited.
