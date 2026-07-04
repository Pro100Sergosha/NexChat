// A short synthesized "exchange chime" for new messages — generated with the
// Web Audio API so there's no binary asset to bundle. Browsers suspend audio
// until a user gesture, so unlockAudio() is wired to the first interaction.

let ctx: AudioContext | null = null;

function getCtx(): AudioContext | null {
  if (typeof window === "undefined" || typeof window.AudioContext === "undefined") {
    return null;
  }
  if (!ctx) ctx = new window.AudioContext();
  return ctx;
}

/** Resume the audio context (call from a user gesture). */
export function unlockAudio(): void {
  const c = getCtx();
  if (c && c.state === "suspended") void c.resume();
}

/** Play a two-note ping. No-op if Web Audio is unavailable. */
export function playPing(): void {
  const c = getCtx();
  if (!c) return;
  if (c.state === "suspended") void c.resume();

  const now = c.currentTime;
  const notes = [
    { freq: 880, at: 0 },
    { freq: 1320, at: 0.09 },
  ];

  for (const n of notes) {
    const osc = c.createOscillator();
    const gain = c.createGain();
    osc.type = "sine";
    osc.frequency.value = n.freq;
    osc.connect(gain);
    gain.connect(c.destination);

    const start = now + n.at;
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(0.14, start + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.25);

    osc.start(start);
    osc.stop(start + 0.3);
  }
}
