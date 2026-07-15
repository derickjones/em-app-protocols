"use client";

/**
 * Voice dictation for the protocol prompt input. One hook, two backends,
 * so platform branching for speech input lives in exactly one place:
 * - Native: @capacitor-community/speech-recognition (on-device SFSpeechRecognizer)
 * - Web: the browser's SpeechRecognition API, behind feature detection
 *
 * Never auto-submits — this is a medical app, the user reviews and edits
 * the dictated text before sending.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Capacitor } from "@capacitor/core";
import { SpeechRecognition } from "@capacitor-community/speech-recognition";

interface WebSpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}

export function useSpeechInput() {
  const [isSupported, setIsSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const webRecognitionRef = useRef<WebSpeechRecognition | null>(null);
  const baseTextRef = useRef("");

  useEffect(() => {
    if (Capacitor.isNativePlatform()) {
      setIsSupported(true);
    } else {
      const w = window as unknown as {
        webkitSpeechRecognition?: new () => WebSpeechRecognition;
        SpeechRecognition?: new () => WebSpeechRecognition;
      };
      setIsSupported(!!(w.webkitSpeechRecognition || w.SpeechRecognition));
    }
  }, []);

  useEffect(() => {
    return () => {
      if (Capacitor.isNativePlatform()) {
        SpeechRecognition.removeAllListeners();
      } else {
        webRecognitionRef.current?.stop();
      }
    };
  }, []);

  const stop = useCallback(async () => {
    if (Capacitor.isNativePlatform()) {
      try {
        await SpeechRecognition.stop();
        await SpeechRecognition.removeAllListeners();
      } catch {
        // already stopped
      }
    } else {
      webRecognitionRef.current?.stop();
    }
    setListening(false);
  }, []);

  const start = useCallback(async (currentText: string, onResult: (text: string) => void) => {
    baseTextRef.current = currentText;

    if (Capacitor.isNativePlatform()) {
      try {
        const { available } = await SpeechRecognition.available();
        if (!available) {
          setIsSupported(false);
          return;
        }
        const perm = await SpeechRecognition.requestPermissions();
        if (perm.speechRecognition !== "granted") {
          setPermissionDenied(true);
          return;
        }
        setPermissionDenied(false);

        await SpeechRecognition.addListener("partialResults", (data: { matches: string[] }) => {
          const words = data.matches?.[0] || "";
          const prefix = baseTextRef.current ? baseTextRef.current + " " : "";
          onResult(prefix + words);
        });

        setListening(true);
        await SpeechRecognition.start({ language: "en-US", partialResults: true, popup: false });
        setListening(false);
      } catch {
        setListening(false);
      }
      return;
    }

    const w = window as unknown as {
      webkitSpeechRecognition?: new () => WebSpeechRecognition;
      SpeechRecognition?: new () => WebSpeechRecognition;
    };
    const SR = w.webkitSpeechRecognition || w.SpeechRecognition;
    if (!SR) return;

    const recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = 0; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      const prefix = baseTextRef.current ? baseTextRef.current + " " : "";
      onResult(prefix + transcript);
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);
    webRecognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  }, []);

  const toggle = useCallback(
    (currentText: string, onResult: (text: string) => void) => {
      if (listening) {
        stop();
      } else {
        start(currentText, onResult);
      }
    },
    [listening, start, stop]
  );

  return { isSupported, listening, permissionDenied, toggle };
}
