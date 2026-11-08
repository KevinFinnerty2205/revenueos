import Image from "next/image";

const avatarStyles = [
  "bg-brand-primary text-white",
  "bg-brand-secondary text-white",
  "bg-amber-100 text-amber-950",
  "bg-sky-100 text-sky-950",
  "bg-rose-100 text-rose-950",
] as const;

export function AccountAvatar({
  accountId,
  name,
  website,
  size = "default",
}: {
  accountId: string;
  name: string;
  website?: string | null;
  size?: "default" | "compact";
}) {
  const style = avatarStyles[stableIndex(accountId, avatarStyles.length)];
  const initials = accountInitials(name);
  const logo = localDemoLogo(website);

  return (
    <span
      aria-hidden="true"
      className={`inline-flex shrink-0 items-center justify-center rounded-xl font-bold ${style} ${
        size === "compact" ? "h-10 w-10 text-sm" : "h-12 w-12 text-base"
      }`}
    >
      {logo ? (
        <Image
          alt=""
          className="h-full w-full rounded-xl"
          height={48}
          src={logo}
          width={48}
        />
      ) : (
        initials
      )}
    </span>
  );
}

function localDemoLogo(website: string | null | undefined): string | null {
  if (!website) return null;
  try {
    const domain = new URL(
      website.startsWith("http://") || website.startsWith("https://")
        ? website
        : `https://${website}`,
    ).hostname.replace(/^www\./u, "");
    if (
      domain === "northstar-facilities.example" ||
      domain === "northstar.example.test"
    ) {
      return "/demo/account-logos/northstar-facilities.svg";
    }
  } catch {
    return null;
  }
  return null;
}

function accountInitials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0]?.slice(0, 2).toUpperCase() ?? "?";
  return `${words[0]?.[0] ?? ""}${words.at(-1)?.[0] ?? ""}`.toUpperCase();
}

function stableIndex(value: string, length: number): number {
  let total = 0;
  for (const character of value)
    total = (total + character.charCodeAt(0)) % length;
  return total;
}
