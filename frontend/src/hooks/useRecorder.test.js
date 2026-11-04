import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { installMediaMocks } from "../test/mediaMocks";
import { useRecorder } from "./useRecorder";

describe("useRecorder", () => {
  let mocks;

  beforeEach(() => {
    mocks = installMediaMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("start() acquires the mic and marks isRecording true", async () => {
    const { result } = renderHook(() => useRecorder());

    await act(async () => {
      await result.current.start();
    });

    expect(mocks.getUserMedia).toHaveBeenCalledWith({ audio: true });
    expect(result.current.isRecording).toBe(true);
  });

  it("stop() releases the mic tracks and marks isRecording false", async () => {
    const { result } = renderHook(() => useRecorder());

    await act(async () => {
      await result.current.start();
    });
    await act(async () => {
      await result.current.stop();
    });

    expect(result.current.isRecording).toBe(false);
    expect(mocks.allTracks[0].stop).toHaveBeenCalled();
  });

  it("stop({ cancel: true }) releases the mic without returning a blob", async () => {
    const { result } = renderHook(() => useRecorder());

    await act(async () => {
      await result.current.start();
    });

    let resolved;
    await act(async () => {
      resolved = await result.current.stop({ cancel: true });
    });

    expect(resolved).toBeNull();
    expect(mocks.allTracks[0].stop).toHaveBeenCalled();
  });

  it("releases the mic on unmount if a recording was left running (regression: logging out mid-recording used to leak the stream indefinitely)", async () => {
    const { result, unmount } = renderHook(() => useRecorder());

    await act(async () => {
      await result.current.start();
    });

    unmount();

    expect(mocks.allTracks[0].stop).toHaveBeenCalled();
  });

  it("unmounting without ever recording does nothing (no error, no phantom stop)", () => {
    const { unmount } = renderHook(() => useRecorder());
    expect(() => unmount()).not.toThrow();
  });
});
