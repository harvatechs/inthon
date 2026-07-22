import React from "react";
import { AbsoluteFill, Sequence, staticFile } from "remotion";
import { Audio } from "@remotion/media";
import { loadFont } from "@remotion/google-fonts/Outfit";
import { SlideText } from "./compositions/InthonDemo/SlideText";
import { ThreeDScene } from "./compositions/InthonDemo/ThreeDScene";

const { fontFamily } = loadFont("normal", {
  weights: ["400", "500", "700"],
  subsets: ["latin"],
});

export const slides = [
  {
    text1: "Get Started",
    text2: "pip install inthon",
  },
  {
    text1: "The World's First",
    text2: "Agent-Level Language",
  },
  {
    text1: "Under the Hood",
    text2: "AST Parser & Stack VM",
  },
  {
    text1: "Bounded Execution",
    text2: "Strictly Sandboxed Policy",
  },
  {
    text1: "Native Primitives",
    text2: "Memory & Approval Gates",
  },
  {
    text1: "PyBridge Interoperability",
    text2: "Secure Python Imports",
  },
  {
    text1: "Token Reductions",
    text2: "Up to 76% Fewer Tokens",
  },
  {
    text1: "One Language for Everything",
    text2: "github.com/harvatechs/inthon",
  },
];

export const getSlideTimings = () => {
  let currentFrame = 0;
  return slides.map((slide, index) => {
    const typingDuration = slide.text1.length + slide.text2.length;
    const holdDuration = 180; // 3 seconds at 60fps
    const duration = typingDuration + holdDuration;
    const startFrame = currentFrame;
    currentFrame += duration;
    return {
      ...slide,
      index,
      startFrame,
      duration,
    };
  });
};

export const Main: React.FC = () => {
  const timings = getSlideTimings();

  return (
    <AbsoluteFill style={{ backgroundColor: "#000000" }}>
      {/* Background Music playing throughout */}
      <Audio
        src={staticFile("assets/music.wav")}
        volume={0.15}
      />

      {timings.map((slide) => {
        const typingFinishFrame = slide.text1.length + slide.text2.length;

        return (
          <Sequence
            key={slide.index}
            name={`Slide ${slide.index + 1}: ${slide.text2}`}
            from={slide.startFrame}
            durationInFrames={slide.duration}
            layout="none"
          >
            {/* 3D Scene for the current slide */}
            <ThreeDScene slideIndex={slide.index} durationInFrames={slide.duration} />

            {/* Typewriter Text Overlay */}
            <SlideText
              text1={slide.text1}
              text2={slide.text2}
              fontFamily={fontFamily}
              durationInFrames={slide.duration}
            />

            {/* Transitional Whoosh Sound */}
            <Audio
              src={staticFile("assets/sfx/whoosh.wav")}
              volume={0.3}
            />

            {/* Soft tick sound at the exact frame the typing completes */}
            <Sequence from={typingFinishFrame} durationInFrames={60} layout="none">
              <Audio
                src={staticFile("assets/sfx/tick.wav")}
                volume={0.4}
              />
            </Sequence>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
