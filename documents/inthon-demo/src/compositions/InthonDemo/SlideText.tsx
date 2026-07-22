import React from "react";
import { useCurrentFrame, interpolate } from "remotion";

interface SlideTextProps {
  text1: string;
  text2: string;
  fontFamily: string;
  durationInFrames: number;
}

export const SlideText: React.FC<SlideTextProps> = ({
  text1,
  text2,
  fontFamily,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();

  const t1Len = text1.length;
  const t2Len = text2.length;

  // Typing logic
  const visibleT1 = frame < t1Len ? text1.slice(0, frame) : text1;
  const t2Frame = frame - t1Len;
  const visibleT2 =
    t2Frame < 0 ? "" : t2Frame < t2Len ? text2.slice(0, t2Frame) : text2;

  // Blinking caret logic
  const showCaret = Math.floor(frame / 12) % 2 === 0;

  // Fade-in at start (15 frames) and Fade-out at end (15 frames)
  const opacity = interpolate(
    frame,
    [0, 15, durationInFrames - 15, durationInFrames],
    [0, 1, 1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  return (
    <div
      style={{
        fontFamily,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        textAlign: "center",
        width: "100%",
        height: "100%",
        padding: "0 100px",
        color: "#ffffff",
        zIndex: 10,
        position: "absolute",
        top: 0,
        left: 0,
        pointerEvents: "none",
        opacity,
      }}
    >
      {/* Supporting Text - Line 1 */}
      <div
        style={{
          fontSize: "36px",
          fontWeight: 500,
          textTransform: "uppercase",
          letterSpacing: "0.25em",
          color: "#a3a3a3",
          marginBottom: "24px",
          minHeight: "44px",
        }}
      >
        {visibleT1}
        {frame < t1Len && (
          <span style={{ color: "#ffffff", marginLeft: "2px", opacity: showCaret ? 1 : 0 }}>|</span>
        )}
      </div>

      {/* Main Headline - Line 2 */}
      <div
        style={{
          fontSize: "90px",
          fontWeight: 700,
          letterSpacing: "-0.03em",
          background: "linear-gradient(180deg, #ffffff 0%, #a3a3a3 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          minHeight: "110px",
          lineHeight: "1.1",
        }}
      >
        {visibleT2}
        {frame >= t1Len && frame < t1Len + t2Len && (
          <span style={{ color: "#ffffff", marginLeft: "2px", opacity: showCaret ? 1 : 0 }}>|</span>
        )}
      </div>
    </div>
  );
};
