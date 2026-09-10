import Image from "next/image";
import Link from "next/link";
import { trialOffer } from "@/lib/marketing";

const productImages = {
  salesBrain: {
    src: "/marketing/product/sales-brain.jpg",
    width: 560,
    height: 780,
  },
  prospect: {
    src: "/marketing/product/prospect.jpg",
    width: 590,
    height: 700,
  },
  engage: {
    src: "/marketing/product/engage.jpg",
    width: 590,
    height: 360,
  },
  create: {
    src: "/marketing/product/create.jpg",
    width: 600,
    height: 720,
  },
  opportunity: {
    src: "/marketing/product/opportunity-workspace.jpg",
    width: 600,
    height: 720,
  },
  pipeline: {
    src: "/marketing/product/pipeline.jpg",
    width: 610,
    height: 900,
  },
  dealRoom: {
    src: "/marketing/product/deal-room.jpg",
    width: 610,
    height: 900,
  },
  handover: {
    src: "/marketing/product/handover.jpg",
    width: 610,
    height: 620,
  },
  analytics: {
    src: "/marketing/product/analytics.jpg",
    width: 430,
    height: 920,
  },
} as const;

export function PageIntro({
  eyebrow,
  title,
  description,
}: Readonly<{ eyebrow: string; title: string; description: string }>) {
  return (
    <header className="mx-auto max-w-4xl text-center">
      <p className="marketing-eyebrow">{eyebrow}</p>
      <h1 className="marketing-page-title mt-5">{title}</h1>
      <p className="mx-auto mt-6 max-w-3xl text-lg leading-8 text-brand-muted sm:text-xl sm:leading-9">
        {description}
      </p>
    </header>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  description,
}: Readonly<{ eyebrow: string; title: string; description?: string }>) {
  return (
    <div className="max-w-3xl">
      <p className="marketing-eyebrow">{eyebrow}</p>
      <h2 className="marketing-section-title mt-4">{title}</h2>
      {description ? (
        <p className="mt-5 text-base leading-8 text-brand-muted sm:text-lg">
          {description}
        </p>
      ) : null}
    </div>
  );
}

export function ProductShot({
  image,
  alt,
  caption,
  captionOnDark = false,
  priority = false,
  className = "",
}: Readonly<{
  image: keyof typeof productImages;
  alt: string;
  caption?: string;
  captionOnDark?: boolean;
  priority?: boolean;
  className?: string;
}>) {
  const asset = productImages[image];
  return (
    <figure className={`min-w-0 ${className}`}>
      <div className="marketing-product-frame">
        <div className="flex items-center gap-1.5 border-b border-brand-primary/10 bg-white px-4 py-3">
          <span className="size-2 rounded-full bg-brand-accent/70" />
          <span className="size-2 rounded-full bg-brand-secondary/35" />
          <span className="size-2 rounded-full bg-brand-primary/20" />
          <span className="ml-3 text-[10px] font-bold uppercase tracking-[0.16em] text-brand-muted">
            Oryntela · synthetic workspace
          </span>
        </div>
        <div className="overflow-hidden bg-[#f8f7f3]">
          <Image
            alt={alt}
            className="h-auto w-full max-w-full"
            height={asset.height}
            priority={priority}
            sizes="(max-width: 639px) calc(100vw - 40px), (max-width: 1023px) 85vw, 600px"
            src={asset.src}
            width={asset.width}
          />
        </div>
      </div>
      {caption ? (
        <figcaption
          className={`mt-3 text-xs leading-5 ${
            captionOnDark ? "text-slate-300" : "text-brand-muted"
          }`}
        >
          {caption}
        </figcaption>
      ) : null}
    </figure>
  );
}

export function TrialCallout({
  heading = "Try the complete Oryntela workflow.",
}: Readonly<{ heading?: string }>) {
  return (
    <section className="marketing-section px-5 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-7xl overflow-hidden rounded-[2rem] bg-brand-primary px-6 py-12 text-brand-primary-foreground shadow-2xl shadow-brand-primary/15 sm:px-10 lg:grid lg:grid-cols-[1fr_auto] lg:items-center lg:gap-12 lg:px-14 lg:py-14">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand-accent">
            {trialOffer.lengthDays}-day trial · Complete
          </p>
          <h2 className="mt-4 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">
            {heading}
          </h2>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300 sm:text-base">
            No card required. No automatic charge. No automatic conversion.
            Public self-service activation remains closed until launch readiness
            is complete.
          </p>
        </div>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row lg:mt-0 lg:flex-col">
          <Link
            href="/contact#trial"
            className="inline-flex min-h-12 items-center justify-center rounded-full bg-white px-6 text-sm font-bold text-brand-primary transition hover:bg-brand-background focus:outline-none focus:ring-2 focus:ring-brand-accent focus:ring-offset-2 focus:ring-offset-brand-primary"
          >
            Request trial access
          </Link>
          <Link
            href="/contact#demo"
            className="inline-flex min-h-12 items-center justify-center rounded-full border border-white/25 px-6 text-sm font-bold text-white transition hover:border-white/50 hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-brand-accent"
          >
            Book a demo
          </Link>
        </div>
      </div>
    </section>
  );
}

export function ArrowLink({
  href,
  children,
}: Readonly<{ href: string; children: React.ReactNode }>) {
  return (
    <Link
      href={href}
      className="group inline-flex min-h-11 items-center gap-2 rounded-lg text-sm font-bold text-brand-secondary focus:outline-none focus:ring-2 focus:ring-brand-focus focus:ring-offset-2"
    >
      {children}
      <span aria-hidden="true" className="transition group-hover:translate-x-1">
        →
      </span>
    </Link>
  );
}
