import React, { useState, useEffect } from 'react';
import { useAccessibility } from '../context/AccessibilityContext';

export const ReadingRuler = () => {
  const { readingRuler } = useAccessibility();
  const [mouseY, setMouseY] = useState(0);

  useEffect(() => {
    if (!readingRuler) return;

    const handlePointerMove = (e) => {
      setMouseY(e.clientY);
    };

    window.addEventListener('pointermove', handlePointerMove, { passive: true });

    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
    };
  }, [readingRuler]);

  if (!readingRuler) return null;

  const highlightHeight = 40; // Height of the highlighted area
  const halfHeight = highlightHeight / 2;

  return (
    <>
      {/* Horizontal line */}
      <div
        className="reading-ruler-line"
        style={{ top: `${mouseY}px` }}
      />

      {/* Highlighted area around the line */}
      <div
        className="reading-ruler-highlight"
        style={{
          top: `${mouseY - halfHeight}px`,
          height: `${highlightHeight}px`,
        }}
      />
    </>
  );
};
