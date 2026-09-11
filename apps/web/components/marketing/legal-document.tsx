import Link from "next/link";

type LegalBlock =
  | { kind: "heading"; level: 2 | 3; text: string; id: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; ordered: boolean; items: string[] };

function headingId(value: string): string {
  return value
    .toLowerCase()
    .replace(/&/gu, "and")
    .replace(/[^a-z0-9]+/gu, "-")
    .replace(/(^-|-$)/gu, "");
}

export function parseLegalDocument(source: string): LegalBlock[] {
  const lines = source.replace(/\r\n/gu, "\n").split("\n");
  const blocks: LegalBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index] ?? "";
    if (!line.trim() || line.startsWith("# ")) {
      index += 1;
      continue;
    }
    if (line.startsWith("> ")) {
      while ((lines[index] ?? "").startsWith("> ")) index += 1;
      continue;
    }

    const heading = /^(##|###)\s+(.+)$/u.exec(line);
    if (heading) {
      const text = heading[2] ?? "";
      blocks.push({
        kind: "heading",
        level: heading[1] === "##" ? 2 : 3,
        text,
        id: headingId(text),
      });
      index += 1;
      continue;
    }

    const unordered = /^-\s+(.+)$/u.exec(line);
    const ordered = /^\d+\.\s+(.+)$/u.exec(line);
    if (unordered || ordered) {
      const isOrdered = Boolean(ordered);
      const items: string[] = [];
      while (index < lines.length) {
        const match = isOrdered
          ? /^\d+\.\s+(.+)$/u.exec(lines[index] ?? "")
          : /^-\s+(.+)$/u.exec(lines[index] ?? "");
        if (!match) break;
        items.push(match[1] ?? "");
        index += 1;
      }
      blocks.push({ kind: "list", ordered: isOrdered, items });
      continue;
    }

    const paragraph: string[] = [];
    while (index < lines.length) {
      const current = lines[index] ?? "";
      if (
        !current.trim() ||
        current.startsWith("#") ||
        current.startsWith("> ") ||
        /^-\s+/u.test(current) ||
        /^\d+\.\s+/u.test(current)
      ) {
        break;
      }
      const hardBreak = current.endsWith("  ");
      paragraph.push(current.trimEnd());
      index += 1;
      if (hardBreak) paragraph.push("\n");
    }
    blocks.push({
      kind: "paragraph",
      text: paragraph.join(" ").replace(/ \n /gu, "\n"),
    });
  }

  return blocks;
}

function linkedText(text: string) {
  const linkPattern =
    /(support@oryntela\.com\.au|hello@oryntela\.com\.au|www\.oaic\.gov\.au)/gu;
  return text.split(linkPattern).map((part, index) => {
    if (
      part === "support@oryntela.com.au" ||
      part === "hello@oryntela.com.au"
    ) {
      return (
        <a
          className="font-semibold text-brand-secondary underline decoration-2 underline-offset-4 focus:outline-none focus:ring-2 focus:ring-brand-focus"
          href={`mailto:${part}`}
          key={`${part}-${index}`}
        >
          {part}
        </a>
      );
    }
    if (part === "www.oaic.gov.au") {
      return (
        <a
          className="font-semibold text-brand-secondary underline decoration-2 underline-offset-4 focus:outline-none focus:ring-2 focus:ring-brand-focus"
          href="https://www.oaic.gov.au/"
          key={`${part}-${index}`}
        >
          {part}
        </a>
      );
    }
    return part;
  });
}

export function LegalDocument({
  source,
  title,
}: Readonly<{ source: string; title: string }>) {
  const blocks = parseLegalDocument(source);
  const sections = blocks.filter(
    (block): block is Extract<LegalBlock, { kind: "heading" }> =>
      block.kind === "heading" && block.level === 2,
  );

  return (
    <section className="px-5 py-12 sm:px-8 sm:py-20 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <header className="max-w-4xl">
          <p className="marketing-eyebrow">Legal document</p>
          <h1 className="marketing-page-title mt-5">{title}</h1>
          <div
            aria-label="Document status"
            className="mt-7 inline-flex rounded-full border border-brand-accent/40 bg-brand-accent/10 px-4 py-2 text-sm font-bold tracking-[0.08em] text-brand-primary"
          >
            OWNER REVIEW DRAFT
          </div>
          <p className="mt-5 max-w-3xl text-sm leading-7 text-brand-muted">
            This review copy is not approved or effective and must not be relied
            on as Oryntela&apos;s published policy. Production publication
            remains blocked until explicit owner approval, an effective date,
            version and content fingerprints are recorded.
          </p>
        </header>

        <div className="mt-12 grid min-w-0 gap-10 lg:grid-cols-[16rem_minmax(0,1fr)] lg:items-start">
          <nav
            aria-label={`${title} sections`}
            className="rounded-2xl border border-brand-primary/10 bg-white p-5 lg:sticky lg:top-24"
          >
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-muted">
              On this page
            </p>
            <ol className="mt-4 space-y-2 text-sm leading-6">
              {sections.map((section) => (
                <li key={section.id}>
                  <a
                    className="block rounded-md text-brand-secondary underline-offset-4 hover:underline focus:outline-none focus:ring-2 focus:ring-brand-focus"
                    href={`#${section.id}`}
                  >
                    {section.text}
                  </a>
                </li>
              ))}
            </ol>
          </nav>

          <article className="min-w-0 rounded-[2rem] border border-brand-primary/10 bg-white p-6 shadow-sm sm:p-10 lg:p-12">
            {blocks.map((block, index) => {
              if (block.kind === "heading") {
                return block.level === 2 ? (
                  <h2
                    className="scroll-mt-24 break-words border-t border-brand-primary/10 pt-10 text-2xl font-semibold leading-tight tracking-[-0.025em] text-brand-primary first:border-0 first:pt-0 sm:text-3xl"
                    id={block.id}
                    key={`${block.id}-${index}`}
                  >
                    {block.text}
                  </h2>
                ) : (
                  <h3
                    className="scroll-mt-24 break-words pt-5 text-xl font-semibold leading-tight text-brand-primary"
                    id={block.id}
                    key={`${block.id}-${index}`}
                  >
                    {block.text}
                  </h3>
                );
              }
              if (block.kind === "list") {
                const List = block.ordered ? "ol" : "ul";
                return (
                  <List
                    className={`mt-5 space-y-3 pl-6 text-[0.95rem] leading-7 text-brand-muted ${
                      block.ordered ? "list-decimal" : "list-disc"
                    }`}
                    key={`list-${index}`}
                  >
                    {block.items.map((item) => (
                      <li className="break-words pl-1" key={item}>
                        {linkedText(item)}
                      </li>
                    ))}
                  </List>
                );
              }
              return (
                <p
                  className="mt-5 whitespace-pre-line break-words text-[0.95rem] leading-7 text-brand-muted"
                  key={`paragraph-${index}`}
                >
                  {linkedText(block.text)}
                </p>
              );
            })}

            <div className="mt-12 border-t border-brand-primary/10 pt-8">
              <Link className="marketing-secondary-button" href="/">
                Return home
              </Link>
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}
