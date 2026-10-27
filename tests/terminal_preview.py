"""Render synthetic terminal previews. Run from the repo: python -m tests.terminal_preview."""
import asyncio
import os
from pathlib import Path

# Preview colors are explicit; the real app still honors NO_COLOR.
os.environ.pop('NO_COLOR', None)
os.environ['COLORTERM'] = 'truecolor'

from tests.helpers import Sandbox
from core.conversation import load_index
from core.overlay import OverlayBackend
from core.provider_registry import PROVIDERS
from core.terminal_ui import WosTerminal, ChoiceScreen
from core.tts import FishAudioSpeaker


async def main():
    target = Path(__file__).resolve().parents[1] / 'docs'
    target.mkdir(exist_ok=True)
    with Sandbox() as sandbox:
        session = sandbox.make_session()
        session.model = 'gemini-example'
        speaker = FishAudioSpeaker({'enabled': False}, notify=lambda *_: None)
        backend = OverlayBackend(lambda: session, speaker)
        app = WosTerminal({'session': session, 'overlay_backend': backend,
            'tts_speaker': speaker, 'load_index': load_index, 'PROVIDERS': PROVIDERS}, startup=False)
        try:
            async with app.run_test(size=(110, 36)) as pilot:
                await pilot.pause(0.3)
                (target / 'terminal-home.svg').write_text(app.export_screenshot(title='Auralis · terminal'), encoding='utf-8')
                await pilot.press('/')
                await pilot.pause()
                (target / 'terminal-commands.svg').write_text(app.export_screenshot(title='Auralis · slash commands'), encoding='utf-8')
                app.composer.load_text('')
                session._record_exchange('Let’s continue our Auralis work.',
                    'Ready, Captain. We can start with a small fix and work from there.\n\n'
                    'Use **F2** to choose a model, or type `/` to explore the commands.')
                backend.hold_command()
                backend.release_command()
                await app.refresh_session()
                await pilot.pause(0.3)
                (target / 'terminal-chat.svg').write_text(app.export_screenshot(title='Auralis · conversation'), encoding='utf-8')
                app.write_output('Auralis: Model changed to gemini-example.\nThis applies to the current chat only.')
                await pilot.pause()
                (target / 'terminal-notice.svg').write_text(app.export_screenshot(title='Auralis · brief notice'), encoding='utf-8')
                await pilot.press('f8')
                await pilot.pause()
                (target / 'terminal-details.svg').write_text(app.export_screenshot(title='Auralis · activity details'), encoding='utf-8')
                await pilot.press('escape', 'ctrl+l', 'ctrl+t')
                await pilot.pause()
                (target / 'terminal-light.svg').write_text(app.export_screenshot(title='Auralis · light theme'), encoding='utf-8')
                await pilot.press('ctrl+t')
                app.push_screen(ChoiceScreen('Available Models', ['gemini-example (current)', 'another-chat-model', 'Other · enter an exact model name']))
                await pilot.pause()
                (target / 'terminal-picker.svg').write_text(app.export_screenshot(title='Auralis · model picker'), encoding='utf-8')
        finally:
            speaker.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
