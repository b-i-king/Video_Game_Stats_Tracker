"use client";

/**
 * SpeechInput — mic button that fills a text field via Web Speech API.
 *
 * Usage:
 *   <SpeechInput onResult={(text) => setStatType(text)} />
 *
 * Falls back silently in unsupported browsers (Safari, Firefox without flag).
 * No external dependency — uses the browser's native SpeechRecognition API.
 */

import { useEffect, useRef, useState } from "react";

interface Props {
  onResult: (text: string) => void;
  /** Placeholder shown in the listening indicator */
  label?: string;
  disabled?: boolean;
}

export default function SpeechInput({ onResult, label = "Listening…", disabled = false }: Props) {
  const [listening, setListening]     = useState(false);
  const [supported, setSupported]     = useState(false);
  const recognitionRef                = useRef<SpeechRecognition | null>(null);

  useEffect(() => {
    const SR =
      (window as Window & { SpeechRecognition?: typeof SpeechRecognition; webkitSpeechRecognition?: typeof SpeechRecognition })
        .SpeechRecognition ??
      (window as Window & { webkitSpeechRecognition?: typeof SpeechRecognition })
        .webkitSpeechRecognition;

    if (!SR) return;
    setSupported(true);

    const rec = new SR();
    rec.lang              = "en-US";
    rec.interimResults    = false;
    rec.maxAlternatives   = 1;
    rec.continuous        = false;

    rec.onresult = (e: SpeechRecognitionEvent) => {
      const transcript = e.results[0][0].transcript.trim();
      onResult(transcript);
    };

    rec.onend  = () => setListening(false);
    rec.onerror = () => setListening(false);

    recognitionRef.current = rec;
  }, [onResult]);

  function toggle() {
    if (!recognitionRef.current) return;
    if (listening) {
      recognitionRef.current.stop();
    } else {
      recognitionRef.current.start();
      setListening(true);
    }
  }

  if (!supported) return null;

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={disabled}
      aria-label={listening ? "Stop listening" : "Start voice input"}
      title={listening ? "Stop" : "Voice input"}
      className={`p-1.5 rounded transition-colors disabled:opacity-40
        ${listening
          ? "text-red-400 animate-pulse bg-red-900/20"
          : "text-[var(--muted)] hover:text-[var(--gold)]"
        }`}
    >
      {listening ? (
        <span className="text-xs font-medium">{label}</span>
      ) : (
        <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" strokeWidth="2"
             strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          <line x1="12" y1="19" x2="12" y2="23"/>
          <line x1="8"  y1="23" x2="16" y2="23"/>
        </svg>
      )}
    </button>
  );
}
