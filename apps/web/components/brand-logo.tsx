import Image from "next/image";

type BrandLogoVariant = "primary" | "dark" | "symbol";

const assets: Record<
  BrandLogoVariant,
  { src: string; width: number; height: number }
> = {
  primary: {
    src: "/brand/oryntela/oryntela-logo-primary.svg",
    width: 480,
    height: 128,
  },
  dark: {
    src: "/brand/oryntela/oryntela-logo-dark.svg",
    width: 480,
    height: 128,
  },
  symbol: {
    src: "/brand/oryntela/oryntela-symbol.svg",
    width: 128,
    height: 128,
  },
};

interface BrandLogoProps {
  className?: string;
  decorative?: boolean;
  variant?: BrandLogoVariant;
}

export function BrandLogo({
  className,
  decorative = false,
  variant = "primary",
}: BrandLogoProps) {
  const asset = assets[variant];
  return (
    <Image
      alt={decorative ? "" : "Oryntela"}
      className={className}
      height={asset.height}
      src={asset.src}
      width={asset.width}
    />
  );
}
