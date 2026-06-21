import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import * as dotenv from "dotenv";
dotenv.config();

const TTS_URL = process.env.TTS_URL;
const MOCK_AI = process.env.MOCK_AI === "true";

export interface SynthResult {
  audioPath: string;
  duration_ms?: number;
  mocked?: boolean;
}

export async function synthesize(text: string): Promise<SynthResult> {
  if (MOCK_AI || !TTS_URL) {
    // Write a minimal valid WAV header (44-byte, 0 samples) as stub
    const wav = Buffer.alloc(44);
    wav.write("RIFF", 0); wav.writeUInt32LE(36, 4);
    wav.write("WAVE", 8); wav.write("fmt ", 12);
    wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22);
    wav.writeUInt32LE(24000, 24); wav.writeUInt32LE(48000, 28);
    wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34);
    wav.write("data", 36); wav.writeUInt32LE(0, 40);

    const outPath = path.join(os.tmpdir(), `viox_tts_mock_${Date.now()}.wav`);
    fs.writeFileSync(outPath, wav);
    return { audioPath: outPath, mocked: true };
  }

  const t0 = Date.now();
  const res = await fetch(`${TTS_URL}/synthesize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!res.ok) throw new Error(`TTS error ${res.status}: ${await res.text()}`);

  const audioBuffer = Buffer.from(await res.arrayBuffer());
  const outPath = path.join(os.tmpdir(), `viox_tts_${Date.now()}.wav`);
  fs.writeFileSync(outPath, audioBuffer);

  return { audioPath: outPath, duration_ms: Date.now() - t0 };
}
