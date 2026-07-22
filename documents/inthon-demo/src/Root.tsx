import React from "react";
import { Composition } from "remotion";
import "./index.css";
import { Main, getSlideTimings } from "./Composition";

// Calculate the total duration in frames dynamically
const timings = getSlideTimings();
const totalDurationInFrames = timings.reduce((sum, slide) => sum + slide.duration, 0);

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="InthonAnnounce"
        component={Main}
        durationInFrames={totalDurationInFrames}
        fps={60}
        width={1920}
        height={1080}
      />
    </>
  );
};
