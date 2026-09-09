This folder is populated automatically by `scripts/prepare_ytdlp_seed.py`
before building with PyInstaller. Run that script first — see
`docs/YT_DLP_UPDATER.md` for why this step exists and what it does.

Nothing needs to be here for normal development (`python main.py`); it's
only used to seed a working yt-dlp copy inside the packaged .exe.
