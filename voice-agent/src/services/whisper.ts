import * as fs from "fs";
import * as dotenv from "dotenv";
dotenv.config();

export interface TranscribeResult {
  text: string;
  language: string;
  duration_ms: number;
  mocked?: boolean;
}

const WHISPER_URL = process.env.WHISPER_URL;
const MOCK_AI = process.env.MOCK_AI === "true";

export async function transcribeAudio(audioPath: string): Promise<TranscribeResult> {
  if (MOCK_AI || !WHISPER_URL) {
    // In mock mode, return the filename stem as fake transcript (useful for testing)
    const stem = audioPath.split("/").pop()?.replace(/\.[^.]+$/, "") ?? "test input";
    return { text: stem, language: "en", duration_ms: 0, mocked: true };
  }

  const audioBuffer = fs.readFileSync(audioPath);
  const blob = new Blob([audioBuffer], { type: "audio/wav" });
  const form = new FormData();
  form.append("file", blob, "audio.wav");

  const res = await fetch(`${WHISPER_URL}/transcribe`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Whisper error ${res.status}: ${await res.text()}`);
  return res.json() as Promise<TranscribeResult>;
}
