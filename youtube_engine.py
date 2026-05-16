#!/usr/bin/env python3
"""
YouTube Channel Reverse Engineering Engine
Claude Channel Model v2 — 12-State Workflow
"""

import os
import sys
import base64
import re
from pathlib import Path
from typing import Optional
import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.rule import Rule
from exporter import export_session_to_docx

console = Console()

# ── System prompt (Claude Channel Model v2) ──────────────────────────────────

SYSTEM_PROMPT = """\
Role
You're acting as my AI YouTube Content Engine. Your job is to analyze, model,
and recreate YouTube content styles while keeping outputs fully original (no
copied wording, only matched style).

How you should respond
- Follow the states in order
- Ask for ONE input at a time
- Stop after each state and wait for my reply
- Don't skip ahead or preview upcoming states
- Keep replies tight — no "Sure!", no "Let me...", no preambles or filler
- Don't summarize what you're about to do; just do the current state

Visual rule
- Don't ask for video/content images before the visual stage (STATE 7)
- Don't think about shot design during script generation
- Exception: Channel branding screenshots (profile, banner, About) in STATE 2 are fine — they inform identity, not shot design.

System flow
1.  Channel to Clone
2.  Channel Name + Screenshots → Branding Brief
3.  Transcripts
4.  Topic / Ideas
5.  Analysis + Style DNA
6.  Script
7.  Visual Input + Analysis
8.  Image Prompts
9.  Video Prompts (optional)
10. Thumbnail Input + Analysis
11. Thumbnails
12. Export Word Document (optional)

─────────────────────────────────────────────────
STATE 1 — Channel to Clone

Ask: "What channel do you want to clone?"
Then stop.

─────────────────────────────────────────────────
STATE 2 — Channel Name + Screenshots → Branding Brief

Ask: "Share the channel name and 2–3 screenshots of the channel (profile,
banner, About page, or featured section) so I can study the branding."
Stop and wait.
Once screenshots are provided, silently analyze:
- Name style and naming logic
- Visual identity (colors, typography, logo feel)
- Banner composition and tone
- Channel description language + positioning
- Target audience signal

Then output only this branding brief (no commentary):
- 5 suggested channel name variants — for a clone channel in this style, not copies of the source name
- 2 channel description variants — short, written in the source channel's voice
- Logo generation prompt — one prompt, style-matched
- Banner generation prompt — one prompt, style-matched
Then stop.

─────────────────────────────────────────────────
STATE 3 — Transcripts

Ask: "Provide 2–3 FULL video transcripts from this channel."
Then stop.

─────────────────────────────────────────────────
STATE 4 — Topic or Ideas

Ask: "Do you want me to generate video ideas or do you already have a topic?"
Then stop.

─────────────────────────────────────────────────
STATE 5 — Analysis + Style DNA

Analyze the transcripts and extract:
- Niche
- Target audience
- Hook style
- Script flow
- Sentence rhythm
- Tone
- Transitions
- Curiosity gaps
- Emotional triggers
- Retention techniques
- Direct address
- Words per second
- Average word count → target word count (±5%)
Don't summarize — extract HOW it works.
Then stop.

─────────────────────────────────────────────────
STATE 6 — Script Generation (style locked)

Generate the full script.
Rules:
- Must match the Style DNA
- Must match pacing and rhythm
- Must match emotional flow
- Must hit target word count
- No generic structures
- Don't think about visuals yet

Before writing: show target word count. After writing: show final word count.
Then stop.

─────────────────────────────────────────────────
STATE 7 — Visual Input + Analysis

Ask: "Upload 3–5 sample video images (NOT thumbnails)."
Analyze and extract:
- Art style
- Color palette
- Lighting style
- Camera style
- Composition
- Detail level
- Mood

Create a Visual Style Profile to use for all subsequent prompts.
Then stop.

─────────────────────────────────────────────────
STATE 8 — Image Prompts (every script beat, max 3–5s each)

Generate image prompts for every script beat.
Rules:
- Each beat = max 3–5 seconds of script
- Each prompt fully standalone
- Each prompt labeled with the exact script segment text
- Don't skip any part of the script
- Each prompt follows the Visual Style Profile exactly

For each beat:
- [Script Segment Text]
- Image Prompt (fully standalone)
- Camera Angle
- Lighting
- Mood
- Action

Standalone prompt rule — each image prompt must:
- Fully describe the scene on its own
- Include subject, environment, lighting, mood, camera
- Name the visual style explicitly
- Not rely on previous prompts

─────────────────────────────────────────────────
STATE 9 — Video Prompts (optional)

Ask: "Do you want me to create video prompts for each image prompt?"
- If yes → generate video prompts for every image prompt
- If no → continue
Then stop.

─────────────────────────────────────────────────
STATE 10 — Thumbnail Input + Analysis

Ask: "Upload 2–3 thumbnail images from the channel."
Analyze and extract:
- Text style
- Composition
- Color contrast
- Emotion triggers
Then stop.

─────────────────────────────────────────────────
STATE 11 — Thumbnails

Generate 5 thumbnails:
- Visual concept
- Text overlay
- Emotion trigger
- Style-matched prompt

─────────────────────────────────────────────────
STATE 12 — Export Word Document (optional)

Ask: "Do you want me to export everything into a Word document?"
- If yes → export all structured content and signal EXPORT_READY
- If no → finish session

─────────────────────────────────────────────────
Always
- Match style, not phrasing
- Each beat = 3–5 seconds max
- Stay in the current state until I reply
"""

# ── Image helpers ─────────────────────────────────────────────────────────────

SUPPORTED_IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def encode_image(path: str) -> tuple[str, str]:
    """Return (base64_data, media_type) for an image file."""
    p = Path(path.strip())
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {p}")
    media_type = SUPPORTED_IMAGE_TYPES.get(p.suffix.lower())
    if not media_type:
        raise ValueError(f"Unsupported image type: {p.suffix}")
    data = base64.standard_b64encode(p.read_bytes()).decode("utf-8")
    return data, media_type


def parse_image_paths(raw: str) -> list[str]:
    """Extract comma/newline-separated image paths from user input."""
    parts = re.split(r"[,\n]+", raw)
    return [p.strip() for p in parts if p.strip()]


# ── Build API message content ────────────────────────────────────────────────

def build_user_content(text: str, image_paths: list[str]) -> list:
    """Build the content list for a Claude API user message."""
    content = []
    for path in image_paths:
        try:
            data, media_type = encode_image(path)
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data},
            })
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[yellow]Warning:[/yellow] {e}")
    if text:
        content.append({"type": "text", "text": text})
    return content if content else [{"type": "text", "text": text}]


# ── Session state ─────────────────────────────────────────────────────────────

class Session:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.history: list[dict] = []
        self.session_log: list[dict] = []  # {role, content_text} for export

    def send(self, text: str, image_paths: list[str] | None = None) -> str:
        image_paths = image_paths or []
        content = build_user_content(text, image_paths)

        self.history.append({"role": "user", "content": content})

        # Log plain text for export
        image_note = f" [+{len(image_paths)} image(s)]" if image_paths else ""
        self.session_log.append({"role": "user", "text": text + image_note})

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=self.history,
        )

        reply = response.content[0].text
        self.history.append({"role": "assistant", "content": reply})
        self.session_log.append({"role": "assistant", "text": reply})
        return reply


# ── Image prompt helpers ──────────────────────────────────────────────────────

IMAGE_STATES = {
    "state 2", "state2", "2",
    "state 7", "state7", "7",
    "state 10", "state10", "10",
}


def prompt_for_images(hint: str) -> list[str]:
    """
    After Claude asks for images, offer the user a chance to provide file paths.
    Returns a list of valid image paths (may be empty).
    """
    console.print()
    console.print(
        "[dim]→ If you have image files to attach, enter their paths "
        "(comma-separated). Press Enter to skip.[/dim]"
    )
    raw = Prompt.ask("[cyan]Image paths[/cyan]", default="").strip()
    if not raw:
        return []
    return parse_image_paths(raw)


def reply_wants_images(reply: str) -> bool:
    """Heuristic: does the assistant reply ask for image uploads?"""
    triggers = [
        "upload", "share", "screenshot", "screenshots", "sample video images",
        "thumbnail images", "provide", "attach",
    ]
    lower = reply.lower()
    return any(t in lower for t in triggers) and (
        "image" in lower or "screenshot" in lower or "thumbnail" in lower
    )


# ── Export detection ──────────────────────────────────────────────────────────

def reply_triggers_export(reply: str) -> bool:
    return "EXPORT_READY" in reply or (
        "export" in reply.lower() and "word" in reply.lower()
        and ("yes" in reply.lower() or "ready" in reply.lower())
    )


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print(
            Panel(
                "[red]ANTHROPIC_API_KEY environment variable is not set.[/red]\n"
                "Export it before running:\n"
                "  [bold]export ANTHROPIC_API_KEY=sk-...[/bold]",
                title="Missing API Key",
            )
        )
        sys.exit(1)

    console.print(
        Panel(
            Text.from_markup(
                "[bold cyan]YouTube Channel Reverse Engineering Engine[/bold cyan]\n"
                "[dim]Claude Channel Model v2 — 12-State Workflow[/dim]\n\n"
                "Type [bold]exit[/bold] or [bold]quit[/bold] to end the session.\n"
                "Type [bold]export[/bold] at any time to save session to a Word doc."
            ),
            border_style="cyan",
        )
    )

    session = Session()

    # Kick off STATE 1 automatically
    console.print(Rule("[dim]Starting session…[/dim]"))
    reply = session.send("Begin.")
    console.print(Panel(reply, title="[bold green]Claude[/bold green]", border_style="green"))

    while True:
        console.print()
        user_input = Prompt.ask("[bold blue]You[/bold blue]").strip()

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            console.print("[dim]Session ended.[/dim]")
            break

        if user_input.lower() == "export":
            path = export_session_to_docx(session.session_log)
            console.print(f"[green]Exported to:[/green] {path}")
            continue

        # Check if we should also ask for images alongside this message
        image_paths: list[str] = []

        reply = session.send(user_input, image_paths)
        console.print()
        console.print(Panel(reply, title="[bold green]Claude[/bold green]", border_style="green"))

        # After Claude replies, if it's asking for images, prompt immediately
        if reply_wants_images(reply):
            image_paths = prompt_for_images(reply)
            if image_paths:
                # Send a follow-up "here are the images" message with the files attached
                follow_up_text = f"Here are the images ({len(image_paths)} file(s) attached)."
                reply2 = session.send(follow_up_text, image_paths)
                console.print()
                console.print(
                    Panel(reply2, title="[bold green]Claude[/bold green]", border_style="green")
                )

        # Export trigger (Claude signals it's ready)
        if reply_triggers_export(reply):
            path = export_session_to_docx(session.session_log)
            console.print(f"\n[green]Session exported to:[/green] {path}")


if __name__ == "__main__":
    main()
