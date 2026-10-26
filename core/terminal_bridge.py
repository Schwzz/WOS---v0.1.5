"""Run the existing command loop on one worker; UI prompts never block rendering."""
import builtins
import queue
import sys
import threading
from dataclasses import dataclass, field


@dataclass
class Output:
    text: str


@dataclass
class Ready:
    pass


@dataclass
class Finished:
    result: str | None = None


@dataclass
class Prompt:
    title: str
    options: list[str] | None = None
    allow_cancel: bool = True
    answer: object = None
    done: threading.Event = field(default_factory=threading.Event)

    def resolve(self, answer):
        if not self.done.is_set():
            self.answer = answer
            self.done.set()


class TerminalBridge:
    def __init__(self, namespace, post):
        self.namespace = namespace
        self.backend = namespace['overlay_backend']
        self.post = post
        self.closed = threading.Event()
        self.commands = queue.Queue(maxsize=1)
        self.thread = None
        self._lock = threading.Lock()
        self._accepting = False
        self._prompt = None

    def emit(self, event):
        if not self.closed.is_set():
            self.post(event)

    def write(self, *values, sep=' ', end='\n', file=None, flush=False):
        if file is not None and file is not sys.stdout:
            builtins.print(*values, sep=sep, end=end, file=file, flush=flush)
            return
        self.emit(Output(sep.join(str(value) for value in values) + end))

    def submit(self, text):
        with self._lock:
            if self.closed.is_set() or not self._accepting:
                return False
            self._accepting = False
            self.commands.put_nowait(text)
            return True

    def ask(self, request):
        with self._lock:
            if self.closed.is_set():
                return None
            self._prompt = request
        self.emit(request)
        request.done.wait()
        with self._lock:
            self._prompt = None
        return request.answer

    def read(self, prompt=''):
        if self.closed.is_set():
            raise EOFError
        if prompt.startswith('You:'):
            with self._lock:
                self._accepting = True
            self.emit(Ready())
            command = self.commands.get()
            if command is None or self.closed.is_set():
                raise EOFError
            return command
        answer = self.ask(Prompt(prompt))
        if answer is None:
            raise EOFError
        return str(answer)

    def choose(self, options, title=None, prompt=None, allow_cancel=True, **_):
        choices = [' '.join(str(option).split()) for option in options]
        if not choices:
            self.write('WOS: There is nothing to choose from.')
            return None
        return self.ask(Prompt(title or 'Choose an option', choices, allow_cancel))

    def start(self):
        self.thread = threading.Thread(target=self._run, name='wos-terminal-commands', daemon=True)
        self.thread.start()

    def _run(self):
        ns = self.namespace
        names = ('input', 'print', 'select_option')
        original = {name: ns[name] for name in names}
        original_notify = self.backend._notify
        original_speech_notify = ns['tts_speaker']._notify
        ns.update(input=self.read, print=self.write, select_option=self.choose)
        self.backend._notify = self.write
        ns['tts_speaker']._notify = self.write
        result = None
        try:
            self.backend.hold_command()
            try:
                if not self.closed.is_set():
                    ns['choose_new_cloud_key_model']()
            except Exception as error:
                self.write(f'WOS: Model setup failed ({type(error).__name__}). Use /model to retry.')
            finally:
                self.backend.release_command()
            while not self.closed.is_set():
                try:
                    result = ns['run_loop']()
                    break
                except Exception as error:
                    # Keep an unexpected command error from killing the UI.
                    # Raw exception text may contain a provider key or request.
                    self.write(f'WOS: Command failed ({type(error).__name__}). Try again.')
                finally:
                    self.backend.release_command()
        except Exception as error:
            self.write(f'WOS: Terminal setup failed ({type(error).__name__}). Restart with --plain.')
        finally:
            self.backend.release_command()
            ns.update(original)
            self.backend._notify = original_notify
            ns['tts_speaker']._notify = original_speech_notify
            self.emit(Finished(result))

    def close(self):
        self.closed.set()
        with self._lock:
            self._accepting = False
            if self._prompt is not None:
                self._prompt.resolve(None)
            try:
                self.commands.put_nowait(None)
            except queue.Full:
                pass
        self.backend.stop_speech()
        if self.thread is not None:
            self.thread.join(timeout=0.2)
