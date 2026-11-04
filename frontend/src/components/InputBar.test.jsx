import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { installMediaMocks } from "../test/mediaMocks";
import InputBar from "./InputBar";

describe("InputBar mic recording", () => {
  let mocks;

  beforeEach(() => {
    mocks = installMediaMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts recording on mic click, showing Cancel/Stop controls", async () => {
    render(<InputBar onSend={vi.fn()} onTranscribe={vi.fn()} />);

    fireEvent.click(screen.getByTitle("Record"));

    await waitFor(() => expect(screen.getByTitle("Stop")).toBeInTheDocument());
    expect(mocks.getUserMedia).toHaveBeenCalledTimes(1);
  });

  it("ignores a second click fired before the first recording has started (duplicate-recording guard)", async () => {
    render(<InputBar onSend={vi.fn()} onTranscribe={vi.fn()} />);

    const micButton = screen.getByTitle("Record");
    // Two rapid clicks with no await in between, simulating a double-click landing before
    // the first getUserMedia() promise has resolved - this is exactly the race the fix in
    // InputBar.jsx (claiming a "starting" state synchronously) closes. Before that fix, both
    // clicks would see mode === "idle" and call recorder.start() twice.
    fireEvent.click(micButton);
    fireEvent.click(micButton);

    await waitFor(() => expect(screen.getByTitle("Stop")).toBeInTheDocument());
    expect(mocks.getUserMedia).toHaveBeenCalledTimes(1);
  });

  it("Cancel stops the recording and releases the mic without producing text", async () => {
    const onSend = vi.fn();
    render(<InputBar onSend={onSend} onTranscribe={vi.fn()} />);

    fireEvent.click(screen.getByTitle("Record"));
    await waitFor(() => expect(screen.getByTitle("Cancel")).toBeInTheDocument());

    fireEvent.click(screen.getByTitle("Cancel"));

    await waitFor(() => expect(screen.getByTitle("Record")).toBeInTheDocument());
    expect(mocks.allTracks[0].stop).toHaveBeenCalled();
    expect(onSend).not.toHaveBeenCalled();
  });

  it("exposes stopRecording() via ref so a parent can drop an active recording on reset (Clear Chat / New Entry)", async () => {
    const ref = createRef();
    render(<InputBar ref={ref} onSend={vi.fn()} onTranscribe={vi.fn()} />);

    fireEvent.click(screen.getByTitle("Record"));
    await waitFor(() => expect(screen.getByTitle("Cancel")).toBeInTheDocument());

    ref.current.stopRecording();

    await waitFor(() => expect(screen.getByTitle("Record")).toBeInTheDocument());
    expect(mocks.allTracks[0].stop).toHaveBeenCalled();
  });

  it("stopRecording() via ref is a no-op when nothing is recording", () => {
    const ref = createRef();
    render(<InputBar ref={ref} onSend={vi.fn()} onTranscribe={vi.fn()} />);

    expect(() => ref.current.stopRecording()).not.toThrow();
    expect(screen.getByTitle("Record")).toBeInTheDocument();
  });
});
