import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement <canvas> - Waveform.jsx calls getContext() purely for drawing,
// which isn't under test here; stub it so that unrelated error noise doesn't clutter output.
HTMLCanvasElement.prototype.getContext = () => null;
