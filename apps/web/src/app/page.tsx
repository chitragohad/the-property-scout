"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import type { SessionSnapshot, TurnResponse } from "@property-scout/schemas";
import { BookingPanel } from "@/components/BookingPanel";
import { EmailShortlistPanel } from "@/components/EmailShortlistPanel";
import { ConfirmSearchCard } from "@/components/ConfirmSearchCard";
import { ConversationHistory } from "@/components/ConversationHistory";
import { ActivePreferencesCompact } from "@/components/ActivePreferences";
import { PreferenceSummary } from "@/components/PreferenceSummary";
import { ShortlistCards } from "@/components/ShortlistCards";
import { SideNav, type NavTab } from "@/components/SideNav";
import { MobileNav } from "@/components/MobileNav";
import { SourcesPanel } from "@/components/SourcesPanel";
import { TopBar } from "@/components/TopBar";
import { TurnInput } from "@/components/TurnInput";
import { VoiceHero } from "@/components/VoiceHero";
import styles from "@/components/companion.module.css";
import {
  checkHealth,
  confirmSearch,
  createBooking,
  createSession,
  exportShortlist,
  fetchBookingSlots,
  fetchHealth,
  getSession,
  postTurn,
  selectListing,
} from "@/lib/api";
import { useVoiceCapture } from "@/lib/useVoiceCapture";
import { applyConfirmResponse, applyTurnResponse } from "@/lib/session-merge";
import {
  initConversationVoice,
  loadVoiceConfig,
  resetConversationVoice,
  speakAssistantReply,
  speakNow,
  stopSpeaking,
  unlockSpeechAudio,
} from "@/lib/tts";

function latestAssistantText(snapshot: SessionSnapshot): string | null {
  for (let i = snapshot.turns.length - 1; i >= 0; i -= 1) {
    const turn = snapshot.turns[i];
    if (
      turn.role === "assistant" &&
      turn.text.trim() &&
      turn.text !== "[confirm-search]"
    ) {
      return turn.text;
    }
  }
  return null;
}

export default function Home() {
  const [snapshot, setSnapshot] = useState<SessionSnapshot | null>(null);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [n8nEnabled, setN8nEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<NavTab>("home");
  const turnCountRef = useRef(0);

  const refreshSession = useCallback(async (sessionId: string) => {
    const next = await getSession(sessionId);
    setSnapshot(next);
    return next;
  }, []);

  const revealTurn = useCallback(
    (apply: (prev: SessionSnapshot) => SessionSnapshot, turn: TurnResponse) => {
      flushSync(() => {
        setSnapshot((prev) => (prev ? apply(prev) : prev));
      });
      speakAssistantReply(turn.assistant_text, turn.shortlist?.length ?? 0, {
        audioBase64: turn.tts_audio_base64,
      });
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      setBusy(true);
      setError(null);
      try {
        const health = await fetchHealth();
        const ok = health.status === "ok";
        if (cancelled) return;
        setApiOk(ok);
        setN8nEnabled(Boolean(health.n8n_enabled));
        if (!ok) {
          setError(
            "API unreachable. Start it with: uvicorn app.main:app --reload --port 8000",
          );
          return;
        }
        await loadVoiceConfig();
        void initConversationVoice();
        unlockSpeechAudio();
        if (cancelled) return;
        const created = await createSession();
        if (cancelled) return;
        resetConversationVoice();
        void initConversationVoice();
        setSnapshot(created);
        turnCountRef.current = created.turns.length;
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to start session");
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    }

    void boot();
    return () => {
      cancelled = true;
      stopSpeaking();
    };
  }, []);

  useEffect(() => {
    if (
      snapshot?.phase === "shortlist" &&
      snapshot.shortlist.length > 0 &&
      activeTab !== "shortlist" &&
      activeTab !== "history"
    ) {
      setActiveTab("shortlist");
    }
  }, [snapshot?.phase, snapshot?.shortlist.length, activeTab]);

  const selectedItem = useMemo(() => {
    if (!snapshot?.shortlist.length) return null;
    const id =
      snapshot.selected_listing_id ?? snapshot.shortlist[0]?.listing.listing_id;
    return snapshot.shortlist.find((item) => item.listing.listing_id === id) ?? null;
  }, [snapshot]);

  const handleTurn = useCallback(
    async (text: string) => {
      if (!snapshot) return;
      setBusy(true);
      setError(null);
      // Keep speechSynthesis warm across the await (mic path has no click gesture).
      unlockSpeechAudio();
      try {
        const turn = await postTurn(snapshot.session_id, text);
        unlockSpeechAudio();
        revealTurn((prev) => applyTurnResponse(prev, text, turn), turn);
        if (
          turn.phase === "shortlist" ||
          (turn.shortlist != null && turn.shortlist.length > 0)
        ) {
          setActiveTab("shortlist");
        }
        void refreshSession(snapshot.session_id)
          .then((next) => {
            setSnapshot(next);
            turnCountRef.current = next.turns.length;
            if (next.phase === "shortlist" && next.shortlist.length > 0) {
              setActiveTab("shortlist");
            }
          })
          .catch(() => {});
      } catch (err) {
        setError(err instanceof Error ? err.message : "Turn failed");
        speakNow("Sorry, I couldn't process that. Please try again.");
      } finally {
        setBusy(false);
      }
    },
    [snapshot, refreshSession, revealTurn],
  );

  const voice = useVoiceCapture({
    disabled: busy || apiOk !== true,
    onSubmit: handleTurn,
  });

  const handleConfirm = useCallback(async () => {
    if (!snapshot) return;
    setBusy(true);
    setError(null);
    // Prime + speak inside the click gesture so post-await TTS is allowed.
    unlockSpeechAudio();
    speakNow("Searching for homes that match your preferences.");
    try {
      const turn = await confirmSearch(snapshot.session_id);
      revealTurn((prev) => applyConfirmResponse(prev, turn), turn);
      if (turn.phase === "shortlist" || (turn.shortlist?.length ?? 0) > 0) {
        setActiveTab("shortlist");
      }
      void refreshSession(snapshot.session_id)
        .then((next) => {
          setSnapshot(next);
          turnCountRef.current = next.turns.length;
          if (next.phase === "shortlist" && next.shortlist.length > 0) {
            setActiveTab("shortlist");
          }
        })
        .catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Confirm failed");
      speakNow("I couldn't complete the search. Please try confirming again.");
    } finally {
      setBusy(false);
    }
  }, [snapshot, refreshSession, revealTurn]);

  const handleSelect = useCallback(
    async (listingId: string) => {
      if (!snapshot) return;
      setBusy(true);
      setError(null);
      try {
        const next = await selectListing(snapshot.session_id, listingId);
        setSnapshot(next);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Selection failed");
      } finally {
        setBusy(false);
      }
    },
    [snapshot],
  );

  const handleEmailExport = useCallback(
    async (email: string) => {
      if (!snapshot) {
        throw new Error("No active session.");
      }
      const result = await exportShortlist(snapshot.session_id, email);
      await refreshSession(snapshot.session_id);
      return result;
    },
    [snapshot, refreshSession],
  );

  const handleBookVisit = useCallback(
    async (listingId: string, date: string, slot: string) => {
      if (!snapshot) {
        throw new Error("No active session.");
      }
      const booking = await createBooking(snapshot.session_id, listingId, date, slot);
      if (!booking) {
        throw new Error("Booking was not created.");
      }
      return booking;
    },
    [snapshot],
  );

  const handleFetchBookingSlots = useCallback(
    async (date: string) => {
      if (!snapshot) {
        return [];
      }
      const body = await fetchBookingSlots(snapshot.session_id, date);
      return body.slots;
    },
    [snapshot],
  );

  const handleRefreshSession = useCallback(async () => {
    if (!snapshot) return;
    await refreshSession(snapshot.session_id);
  }, [snapshot, refreshSession]);

  const handleNewSearch = useCallback(async () => {
    setBusy(true);
    setError(null);
    stopSpeaking();
    try {
      const ok = await checkHealth();
      setApiOk(ok);
      if (!ok) {
        setError("API unreachable. Start the API server first.");
        return;
      }
      const health = await fetchHealth();
      setN8nEnabled(Boolean(health.n8n_enabled));
      const created = await createSession();
      resetConversationVoice();
      void initConversationVoice();
      setSnapshot(created);
      setActiveTab("home");
      turnCountRef.current = created.turns.length;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start new session");
    } finally {
      setBusy(false);
    }
  }, []);

  const showIdleHome =
    snapshot?.phase === "idle" &&
    snapshot.turns.filter((t) => t.text !== "[confirm-search]").length === 0;

  const showChatHome =
    snapshot &&
    !showIdleHome &&
    (snapshot.phase === "clarifying" ||
      snapshot.phase === "awaiting_confirm" ||
      snapshot.phase === "booking");

  const prefInsight = snapshot ? latestAssistantText(snapshot) : null;

  return (
    <div className={styles.page}>
      <SideNav
        activeTab={activeTab}
        shortlistCount={snapshot?.shortlist.length ?? 0}
        onTabChange={setActiveTab}
        onNewSearch={handleNewSearch}
        newSearchDisabled={busy}
      />

      <div className={styles.mainShell}>
        {snapshot && (
          <TopBar
            phase={snapshot.phase}
            apiOk={apiOk}
            ttsSupported={voice.ttsSupported}
            ttsOn={voice.ttsOn}
            onTtsToggle={voice.handleTtsToggle}
          />
        )}

        {error && (
          <div className={styles.errorBanner} role="alert">
            {error}
          </div>
        )}

        {snapshot && (
          <>
            <div className={styles.contentScroll}>
              <div className={styles.contentInner}>
                {activeTab === "home" && (
                  <>
                    {showIdleHome && (
                      <>
                        <header className={styles.homeHeader}>
                          <div>
                            <h2>Find your next home</h2>
                            <p>
                              Let&apos;s narrow down exactly what you&apos;re looking for
                              in Bengaluru.
                            </p>
                          </div>
                        </header>
                        <div className={styles.homeGrid}>
                          <VoiceHero
                            disabled={busy || apiOk !== true}
                            listening={voice.listening}
                            liveTranscript={voice.liveTranscript}
                            voiceHint={voice.voiceHint}
                            sttSupported={voice.sttSupported}
                            micLabel={voice.micLabel}
                            onMicClick={voice.handleMicClick}
                          />
                          <PreferenceSummary
                            constraints={snapshot.constraints}
                            phase={snapshot.phase}
                            clarificationCount={snapshot.clarification_count}
                          />
                        </div>
                      </>
                    )}

                    {showChatHome && (
                      <div className={styles.chatGrid}>
                        <div className={styles.chatColumn}>
                          <div className={styles.chatScroll}>
                            <ConversationHistory
                              turns={snapshot.turns}
                              pending={busy}
                              compact
                            />
                            {snapshot.phase === "awaiting_confirm" && (
                              <ConfirmSearchCard
                                constraints={snapshot.constraints}
                                disabled={busy || apiOk !== true}
                                onConfirm={handleConfirm}
                              />
                            )}
                            {(snapshot.phase === "booking" || snapshot.booking) && (
                              <BookingPanel
                                sessionId={snapshot.session_id}
                                booking={snapshot.booking ?? null}
                                selectedItem={selectedItem}
                                disabled={busy || apiOk !== true}
                                onBook={handleBookVisit}
                                onFetchSlots={handleFetchBookingSlots}
                                onRefresh={handleRefreshSession}
                              />
                            )}
                          </div>
                        </div>
                        <PreferenceSummary
                          constraints={snapshot.constraints}
                          phase={snapshot.phase}
                          clarificationCount={snapshot.clarification_count}
                          insight={prefInsight}
                        />
                      </div>
                    )}

                  </>
                )}

                {activeTab === "shortlist" && (
                  <div className={styles.shortlistLayout}>
                    <div className={styles.shortlistMain}>
                      <ShortlistCards
                        items={snapshot.shortlist}
                        selectedId={
                          snapshot.selected_listing_id ??
                          snapshot.shortlist[0]?.listing.listing_id ??
                          null
                        }
                        onSelect={handleSelect}
                      />
                      <EmailShortlistPanel
                        listingCount={snapshot.shortlist.length}
                        deliveryEnabled={n8nEnabled}
                        disabled={busy || apiOk !== true}
                        onSubmit={handleEmailExport}
                      />
                      <BookingPanel
                        sessionId={snapshot.session_id}
                        booking={snapshot.booking ?? null}
                        selectedItem={selectedItem}
                        disabled={busy || apiOk !== true}
                        onBook={handleBookVisit}
                        onFetchSlots={handleFetchBookingSlots}
                        onRefresh={handleRefreshSession}
                      />
                    </div>
                    <aside className={styles.shortlistAside}>
                      <ActivePreferencesCompact constraints={snapshot.constraints} />
                      <SourcesPanel
                        item={selectedItem}
                        sessionCitations={snapshot.citations}
                      />
                    </aside>
                  </div>
                )}

                {activeTab === "history" && (
                  <section className={`${styles.panel} ${styles.historyPanel}`}>
                    <div className={styles.panelHeader}>
                      <h2>Conversation History</h2>
                    </div>
                    <ConversationHistory turns={snapshot.turns} pending={busy} />
                  </section>
                )}
              </div>
            </div>

            {(activeTab === "home" || activeTab === "shortlist") && (
              <TurnInput
                phase={snapshot.phase}
                disabled={busy || apiOk !== true}
                onSubmit={handleTurn}
                listening={voice.listening}
                sttSupported={voice.sttSupported}
                onMicClick={voice.handleMicClick}
                micLabel={voice.micLabel}
              />
            )}

            <MobileNav
              activeTab={activeTab}
              shortlistCount={snapshot.shortlist.length}
              onTabChange={setActiveTab}
            />
          </>
        )}
      </div>
    </div>
  );
}
