# WOS-Overlay

WOS plus a desktop window for Nexis: an animated core that shows what WOS is
doing, a chat panel, and a **Voice Output** switch. The window is a second
view onto the *same* running WOS process, so the provider, character, memory,
chats and TTS are shared with the terminal. Nothing is duplicated.

## Run

    pip install -r requirements.txt
    run.bat

`run.bat` opens the overlay window (it waits for WOS) and starts the normal
WOS terminal with `python start.py --overlay`. Plain `python start.py` still
works exactly as before and starts no overlay. `run.bat --browser` opens the
overlay in your browser instead. Without `pywebview` the browser is used
automatically.

## How it fits together

- `core/overlay.py` - `OverlayBackend` (one lock shared by the terminal loop
  and the UI, so they never change the session at the same time) and a small
  local HTTP server on `127.0.0.1` (port from `settings.json` ->
  `overlay.port`, default 47615; `0` = any free port). Every API call needs a
  random token that `overlay/main.py` reads from `data/overlay_endpoint.json`.
- `core/tts.py` - the single Fish Audio speaker. It now also reports
  `queued / start / end` and the loudness of the WAV it is about to play;
  that is what drives the avatar.
- `overlay/main.py` - the pywebview window. `overlay/web/` - the Sage Companion
  renderer (`sage.js`, `style.css`) plus `chat.js` for chat, voice and the
  backend link.
- The terminal keeps all its commands. The overlay is chat only: text starting
  with `/` is refused there ("run it in the terminal").

## Voice Output

`settings.json` -> `tts.enabled`, default `false`. The overlay switch and the
terminal use that one setting, so toggling in the window changes it for both
and it is remembered next start. `FISH_AUDIO_API_KEY` must be set (environment
variable or `.env`); the key is never sent to the UI. If voice is on but the
key is missing the button says `voice: on (no key)`.

## Manual Windows test

1. `pip install -r requirements.txt`, then double-click `run.bat`.
   Expect a terminal (normal WOS header) and a small always-on-top window
   (bottom-right) that says `waiting for WOS`, then `standing by`.
2. Click `chat`. The window grows upward and a chat panel appears.
   Type `hello` and press Enter. Expect:
   - the core switches to `thinking` (faster spin) while the model works;
   - the reply appears in the panel and in the terminal as
     `You (overlay): hello` / `Nexis: ...`;
   - back to `idle`. Click `avatar` to collapse; the last reply shows as one
     line under the readout.
3. In the terminal type `hello again`, then check the panel updates and the
   core also showed `thinking`. Run `/memory`, `/chats`: same session.
4. Voice off (default, `voice: off`): replies are text only, no sound, no
   request to Fish Audio.
5. Set `FISH_AUDIO_API_KEY`, restart, click `voice: off` -> `voice: on`.
   Send a message. Expect `thinking` until the audio starts, then `speaking`
   with the core pulsing in time with your own voice's loud and quiet parts
   (try a long and a very short reply), then `idle` the moment it stops.
   A reply typed in the terminal is spoken and animated the same way.
6. Close WOS, reopen: the voice switch keeps its last position
   (`settings.json` -> `tts.enabled`). Switching it off mid-speech stops it.
7. Type `/restart` in the terminal. The overlay shows `backend offline` for a
   few seconds, then reconnects by itself.
8. Type `/exit`. The overlay window closes about 20 seconds later.

## Known limitations

- Not run on a real Windows desktop by the automated tests: window resize,
  dragging, `winsound` playback and the pywebview shell are untested there.
  The backend, HTTP API, speech events, loudness data and `chat.js` logic are
  covered by tests (`tests/test_overlay.py`, `tests/js/chat_harness.js`).
- Avatar timing follows the moment playback starts, plus network latency
  (about 150 ms polling); expect it to be slightly loose, not frame-exact.
- `easy_drag` (drag the window anywhere) may make selecting text in the chat
  log awkward; the input box is unaffected.
- A UI message waits up to 3 seconds if the terminal is in the middle of a
  command (for example a model picker), then reports "busy".
