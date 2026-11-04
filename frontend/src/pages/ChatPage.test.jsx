import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../services/api";
import ChatPage from "./ChatPage";

vi.mock("../services/api", async () => {
  const actual = await vi.importActual("../services/api");
  return {
    ...actual,
    createSession: vi.fn(),
    getSession: vi.fn(),
    resumeSession: vi.fn(),
    submitBatchAnswer: vi.fn(),
    correctField: vi.fn(),
    confirmSession: vi.fn(),
    transcribeAudio: vi.fn(),
  };
});

import { getSession } from "../services/api";

const SESSION_KEY = "vda_session_id";
const LANGUAGE_KEY = "vda_language";

describe("ChatPage session recovery", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it("shows the language picker on a completely fresh load (no session, no language)", () => {
    render(<ChatPage token="tok" username="op" onLogout={vi.fn()} />);
    expect(screen.getByText(/choose a language/i)).toBeInTheDocument();
    expect(getSession).not.toHaveBeenCalled();
  });

  it("resumes an existing session on reload instead of showing the picker", async () => {
    sessionStorage.setItem(SESSION_KEY, "sess-1");
    sessionStorage.setItem(LANGUAGE_KEY, "en");
    getSession.mockResolvedValue({
      session_id: "sess-1",
      state: "COLLECTING",
      language: "en",
      questions: [],
      answered_field_keys: [],
    });

    render(<ChatPage token="tok" username="op" onLogout={vi.fn()} />);

    await waitFor(() => expect(getSession).toHaveBeenCalledWith("tok", "sess-1"));
    expect(screen.queryByText(/choose a language/i)).not.toBeInTheDocument();
  });

  it("shows the language picker again after a completed+reloaded entry, instead of a silently dead input bar (regression)", () => {
    // No SESSION_KEY (cleared when a session reaches COMPLETED) but LANGUAGE_KEY is still set
    // from that finished entry. Before the fix, this combination skipped both the picker and
    // boot(), landing on a rendered InputBar whose handleSend() silently no-op'd because
    // there was no sessionIdRef.current to submit against.
    sessionStorage.setItem(LANGUAGE_KEY, "en");

    render(<ChatPage token="tok" username="op" onLogout={vi.fn()} />);

    expect(screen.getByText(/choose a language/i)).toBeInTheDocument();
    expect(getSession).not.toHaveBeenCalled();
  });

  it("falls back to the language picker if resuming a stale session fails", async () => {
    sessionStorage.setItem(SESSION_KEY, "sess-stale");
    getSession.mockRejectedValue(new ApiError("not found", 404));

    render(<ChatPage token="tok" username="op" onLogout={vi.fn()} />);

    await waitFor(() => expect(screen.getByText(/choose a language/i)).toBeInTheDocument());
  });

  it("logs out instead of retrying when the session token itself is invalid (401)", async () => {
    sessionStorage.setItem(SESSION_KEY, "sess-1");
    getSession.mockRejectedValue(new ApiError("unauthorized", 401));
    const onLogout = vi.fn();

    render(<ChatPage token="tok" username="op" onLogout={onLogout} />);

    await waitFor(() => expect(onLogout).toHaveBeenCalled());
  });
});
