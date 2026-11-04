import { vi } from "vitest";

// Minimal fakes for the Web Audio / MediaRecorder APIs jsdom doesn't implement, just enough
// for useRecorder's start()/stop() lifecycle and InputBar's mic flow to run in tests.
export function installMediaMocks() {
  const allTracks = [];

  class FakeTrack {
    constructor() {
      this.stop = vi.fn();
    }
  }

  class FakeStream {
    constructor() {
      this._tracks = [new FakeTrack()];
      allTracks.push(...this._tracks);
    }
    getTracks() {
      return this._tracks;
    }
  }

  class FakeMediaRecorder {
    constructor(stream) {
      this.stream = stream;
      this.state = "inactive";
      this.ondataavailable = null;
      this.onstop = null;
      this.mimeType = "audio/webm";
      FakeMediaRecorder.instances.push(this);
    }
    start() {
      this.state = "recording";
    }
    stop() {
      this.state = "inactive";
      if (this.onstop) this.onstop();
    }
  }
  FakeMediaRecorder.instances = [];

  class FakeAudioContext {
    createMediaStreamSource() {
      return { connect: vi.fn() };
    }
    createAnalyser() {
      return { fftSize: 2048, getByteTimeDomainData: vi.fn() };
    }
    close() {
      return Promise.resolve();
    }
  }

  const getUserMedia = vi.fn().mockImplementation(() => Promise.resolve(new FakeStream()));

  vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
  vi.stubGlobal("AudioContext", FakeAudioContext);
  vi.stubGlobal("requestAnimationFrame", vi.fn(() => 1));
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
  Object.defineProperty(window.navigator, "mediaDevices", {
    value: { getUserMedia },
    configurable: true,
  });

  return { FakeMediaRecorder, getUserMedia, allTracks };
}
