"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { Booking, ShortlistItem } from "@property-scout/schemas";
import { MaterialIcon } from "./MaterialIcon";
import styles from "./companion.module.css";

type Props = {
  sessionId: string;
  booking: Booking | null;
  selectedItem: ShortlistItem | null;
  disabled?: boolean;
  onBook: (listingId: string, date: string, slot: string) => Promise<Booking>;
  onFetchSlots: (date: string) => Promise<string[]>;
  onRefresh: () => Promise<void>;
};

function formatSlot(slot: string): string {
  const [hourRaw, minuteRaw] = slot.split(":");
  const hour = Number(hourRaw);
  const minute = Number(minuteRaw);
  const suffix = hour < 12 ? "AM" : "PM";
  const displayHour = hour % 12 || 12;
  if (minute) {
    return `${displayHour}:${String(minute).padStart(2, "0")} ${suffix}`;
  }
  return `${displayHour} ${suffix}`;
}

function defaultVisitDate(): string {
  const now = new Date();
  const day = now.getDay();
  const daysUntilSaturday = (6 - day + 7) % 7 || 7;
  const target = new Date(now);
  target.setDate(now.getDate() + daysUntilSaturday);
  return target.toISOString().slice(0, 10);
}

export function BookingPanel({
  sessionId,
  booking,
  selectedItem,
  disabled,
  onBook,
  onFetchSlots,
  onRefresh,
}: Props) {
  const [visitDate, setVisitDate] = useState(booking?.date || defaultVisitDate());
  const [selectedSlot, setSelectedSlot] = useState(booking?.slot ?? "");
  const [slots, setSlots] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const listingId = selectedItem?.listing.listing_id ?? booking?.listing_id ?? null;
  const societyName = selectedItem?.listing.society_name ?? "Selected home";
  const confirmed = booking?.status === "confirmed" && Boolean(booking.confirmation_code);

  const loadSlots = useCallback(async () => {
    if (!sessionId || !visitDate) return;
    try {
      const next = await onFetchSlots(visitDate);
      setSlots(next);
      if (next.length && !next.includes(selectedSlot)) {
        setSelectedSlot(next[0] ?? "");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load slots.");
    }
  }, [onFetchSlots, selectedSlot, sessionId, visitDate]);

  useEffect(() => {
    void loadSlots();
  }, [loadSlots]);

  useEffect(() => {
    if (booking?.date) setVisitDate(booking.date);
    if (booking?.slot) setSelectedSlot(booking.slot);
  }, [booking?.date, booking?.slot]);

  const slotButtons = useMemo(
    () =>
      slots.map((slot) => (
        <button
          key={slot}
          type="button"
          className={styles.bookingSlotButton}
          data-selected={selectedSlot === slot || undefined}
          disabled={disabled || busy || confirmed}
          onClick={() => setSelectedSlot(slot)}
        >
          {formatSlot(slot)}
        </button>
      )),
    [busy, confirmed, disabled, selectedSlot, slots],
  );

  async function handleConfirm() {
    if (!listingId || !visitDate || !selectedSlot) {
      setError("Choose a date and time slot.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onBook(listingId, visitDate, selectedSlot);
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Booking failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!listingId) {
    return null;
  }

  return (
    <section className={styles.bookingPanel} aria-labelledby="booking-heading">
      <div className={styles.bookingPanelHeader}>
        <h2 id="booking-heading">
          <MaterialIcon name="event_available" />
          Site visit booking
        </h2>
        <p>
          Schedule a visit to <strong>{societyName}</strong>. You can also say
          &ldquo;visit Saturday at 4 PM&rdquo; by voice.
        </p>
      </div>

      {confirmed && booking ? (
        <div className={styles.bookingConfirmed} role="status">
          <p className={styles.bookingConfirmedTitle}>Visit confirmed</p>
          <dl className={styles.bookingDetails}>
            <div>
              <dt>Date</dt>
              <dd>{visitDate}</dd>
            </div>
            <div>
              <dt>Time</dt>
              <dd>{formatSlot(booking.slot)}</dd>
            </div>
            <div>
              <dt>Confirmation code</dt>
              <dd className={styles.bookingCode}>{booking.confirmation_code}</dd>
            </div>
          </dl>
        </div>
      ) : (
        <>
          <label className={styles.bookingLabel} htmlFor="visit-date">
            Preferred date
          </label>
          <input
            id="visit-date"
            type="date"
            className={styles.bookingDateInput}
            value={visitDate}
            disabled={disabled || busy}
            onChange={(event) => setVisitDate(event.target.value)}
          />

          <p className={styles.bookingSlotsLabel}>Available slots</p>
          {slots.length ? (
            <div className={styles.bookingSlotGrid}>{slotButtons}</div>
          ) : (
            <p className={styles.bookingEmptySlots}>No open slots on this date.</p>
          )}

          <button
            type="button"
            className={styles.bookingConfirmButton}
            disabled={disabled || busy || !selectedSlot}
            onClick={handleConfirm}
          >
            {busy ? "Confirming…" : "Confirm visit"}
            {!busy && <MaterialIcon name="check_circle" />}
          </button>
        </>
      )}

      {error && (
        <p className={styles.bookingError} role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
