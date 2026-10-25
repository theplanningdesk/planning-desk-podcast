import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';

// Fades each scene in and out so cuts between graphics never feel abrupt.
export const Scene = ({dur, bare, children}) => {
  const frame = useCurrentFrame();
  const fadeIn = bare ? 1 : interpolate(frame, [0, 8], [0, 1], {extrapolateRight: 'clamp'});
  const fadeOut = interpolate(frame, [dur - 8, dur], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  // Slow push-in so a graphic never sits perfectly still.
  const push = 1;
  const drift = bare ? 0 : interpolate(frame, [0, 10], [12, 0], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{opacity: Math.min(fadeIn, dur > 16 ? fadeOut : 1), transform: `scale(${push}) translateY(${drift}px)`, transformOrigin: '50% 45%'}}>
      {children}
    </AbsoluteFill>
  );
};

// Shared entrance helper: 0 to 1 over `len` frames after `delay`, eased.
export const useEnter = (delay = 0, len = 18) => {
  const frame = useCurrentFrame();
  const x = interpolate(frame, [delay, delay + len], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return 1 - Math.pow(1 - x, 3);
};
