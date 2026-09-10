import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";

export const alt = "Oryntela — one sales system from prospect to handover";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const wordmark = await readFile(
  join(process.cwd(), "public/brand/oryntela/oryntela-wordmark.svg"),
);
const wordmarkData = `data:image/svg+xml;base64,${wordmark.toString("base64")}`;

export default function OpenGraphImage() {
  return new ImageResponse(
    <div
      style={{
        alignItems: "stretch",
        background: "#F6F4EF",
        color: "#0E1B32",
        display: "flex",
        height: "100%",
        justifyContent: "space-between",
        overflow: "hidden",
        padding: "72px",
        position: "relative",
        width: "100%",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          width: "800px",
        }}
      >
        <img alt="" height={76} src={wordmarkData} width={300} />
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            style={{
              color: "#204E5A",
              fontSize: "22px",
              fontWeight: 700,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
            }}
          >
            End-to-end sales platform
          </div>
          <div
            style={{
              fontSize: "64px",
              fontWeight: 700,
              letterSpacing: "-0.045em",
              lineHeight: 1.04,
              marginTop: "24px",
            }}
          >
            One sales system from prospect to handover.
          </div>
        </div>
      </div>
      <div
        aria-hidden="true"
        style={{
          alignItems: "center",
          background: "#0E1B32",
          borderRadius: "46px",
          display: "flex",
          height: "100%",
          justifyContent: "center",
          position: "relative",
          width: "245px",
        }}
      >
        <svg height="170" viewBox="0 0 128 128" width="170">
          <g
            fill="none"
            stroke="#F6F4EF"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="14"
          >
            <path d="M81 22C49 12 22 34 22 66c0 31 25 51 54 43" />
            <path d="m51 108 55-87" />
          </g>
          <path
            d="m96 37 10-16"
            fill="none"
            stroke="#C96B45"
            strokeLinecap="round"
            strokeWidth="14"
          />
        </svg>
      </div>
    </div>,
    size,
  );
}
