# Contributing to Miscoshorts AI

Thanks for wanting to help! Bug reports, ideas and pull requests are all welcome.

## Reporting a bug

[Open an issue](https://github.com/JoaquinRuiz/miscoshorts-ai/issues/new) with:

- what you ran (the command and the env vars you set, **without API keys**),
- what you expected and what happened, including the full error,
- your OS, Python version, `ffmpeg -version` and backend (Gemini, Ollama, LM Studio, llama.cpp, whisper-server…).

## Suggesting a feature

Open an issue first describing the use case, so we can agree on the approach before you write code. Small fixes (typos, docs, obvious bugs) can go straight to a pull request.

## Development setup

```bash
git clone https://github.com/JoaquinRuiz/miscoshorts-ai.git
cd miscoshorts-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

You also need FFmpeg in your `PATH`. To test without a Gemini key, run fully local (see [Run it 100% local](README.md#run-it-100-local)).

## Pull requests

1. Fork the repo and create a branch from `main`.
2. Keep the change focused: one feature or fix per pull request.
3. **Don't break the default setup.** Gemini + local Whisper must keep working with no extra configuration; new backends or behaviour should be opt-in through environment variables.
4. Keep every backend interchangeable: transcription returns Whisper-style `segments` (`start`, `end`, `text`) and each `cerebro_*.py` exposes `encontrar_clip_viral(segments)` returning the `TITULO / INICIO / FIN / RAZON` text format.
5. Test it end to end on a real video with the backends you touched, and say which ones in the pull request.
6. Update the README if you add or change a setting.

The code mixes Spanish (function names, prompts, console messages) and English (docs, comments). Follow the style of the file you are editing.

## Never commit secrets

Don't commit API keys, `.env` files or generated media. If you paste your Gemini key into `cerebro_gemini.py` to test, revert that line before committing.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
