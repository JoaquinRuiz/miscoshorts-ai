# Miscoshorts - AI-Powered YouTube Shorts Generator

Automatically creates viral YouTube Shorts from long-form videos using AI analysis and automatic subtitle generation.
🎥 **[WATCH YOUTUBE TUTORIAL](https://youtu.be/zukJLVUwMxA?si=_DQ2RG10uzXtt7yT)**

## Features

- 🎥 Downloads YouTube videos automatically
- 🔍 Transcribes audio using Whisper (local or OpenAI‑compatible API)
- 🤖 Analyzes content with Google Gemini or any OpenAI-compatible API (Ollama, LM Studio, llama.cpp) to find viral segments
- ✂️ Crops videos to vertical 9:16 format for Shorts
- 📝 Generates automatic subtitles with styling
- 🎬 Creates ready-to-upload MP4 files

## Requirements

- Python 3.12+
- FFmpeg (required by moviepy)
- Google Gemini API key

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd miscoshorts
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install FFmpeg:
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

4. Set up your Google Gemini API key:
   - Get an API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Update the `GEMINI_API_KEY` variable in `cerebro_gemini.py`

5. (Optional) Run fully local instead of Gemini + local Whisper. Everything is configured with environment variables:

   | Variable | Default | Purpose |
   |---|---|---|
   | `CEREBRO_BACKEND` | `gemini` | `openai` to use any OpenAI-compatible API (Ollama, LM Studio, llama.cpp...) |
   | `OPENAI_BASE_URL` | `http://localhost:11434/v1` | API endpoint. Ollama `11434`, LM Studio `1234`, llama.cpp `8080` |
   | `OPENAI_MODEL` | `qwen3:30b` | Model name as your server exposes it |
   | `OPENAI_API_KEY` | `none` | Only needed if your server requires one |
   | `USE_WHISPER_API` | `false` | `true` to transcribe with a remote whisper.cpp `whisper-server` |
   | `WHISPER_API_URL` | `http://localhost:9191/inference` | whisper-server endpoint |

   Example:
   ```bash
   CEREBRO_BACKEND=openai OPENAI_MODEL=qwen3:30b USE_WHISPER_API=true \
     python maker.py "https://www.youtube.com/watch?v=VIDEO_ID"
   ```

## Usage

1. Run the script with the YouTube URL (or edit `URL_VIDEO` in `maker.py`):
```bash
python maker.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

3. The script will:
   - Download the video
   - Transcribe the audio
   - Ask the AI (Gemini by default) to suggest the best viral segment
   - Show you the suggestion with title, timestamps, and reasoning
   - Ask for confirmation (press 's' to accept or provide custom timestamps)
   - Generate the vertical Short with subtitles
   - Save as `short_con_subs.mp4`

## Configuration

### Video Settings
Edit these variables in `maker.py`:
- `URL_VIDEO`: YouTube video URL to process
- `NOMBRE_SALIDA`: Output filename (default: "short_con_subs.mp4")

### Subtitle Styling
Edit subtitle appearance in `subtitulos.py`:
- Font: `DejaVuSans-Bold` (change to any available system font)
- Font size: `70`
- Color: `yellow` with black stroke
- Position: Centered

### AI Analysis
Edit the prompt in `cerebro_gemini.py` to customize how Gemini analyzes videos for viral potential.

## Output Files

- `short_con_subs.mp4`: Final vertical Short with subtitles
- `transcripcion_completa.txt`: Full transcription with timestamps
- `video_temp.mp4`: Temporary downloaded video (auto-deleted)

## Troubleshooting

### Font Issues
If you encounter font errors, try these alternatives:
- `'LiberationSans-Bold'`
- `'Arial-Bold'` 
- `'Ubuntu-Bold'`

Or install fonts:
```bash
sudo apt install fonts-dejavu-core fonts-liberation
```

### MoviePy Issues
Ensure FFmpeg is installed and in your PATH:
```bash
ffmpeg -version
```

### Whisper Issues
The script uses `openai-whisper`. If you have the wrong whisper package:
```bash
pip uninstall whisper
pip install openai-whisper
```

> **Tip:** To use a remote whisper.cpp server, set `USE_WHISPER_API=true` and `WHISPER_API_URL` (e.g. `http://localhost:9191/inference`). The audio is extracted to 16 kHz WAV with ffmpeg before uploading, and the server must support `response_format=srt`.

### Gemini API Issues
- Make sure your API key is valid
- Check that you're using the correct model name (`gemini-2.5-flash`)
- Monitor your API usage to avoid rate limits

## File Structure

```
miscoshorts/
├── maker.py              # Main script
├── cerebro_gemini.py     # Gemini AI analysis
├── cerebro_openai.py     # OpenAI-compatible AI analysis (Ollama, LM Studio, llama.cpp)
├── subtitulos_whisper.py # Transcription (local Whisper or whisper-server API)
├── subtitulos.py         # Subtitle generation
├── requirements.txt      # Python dependencies
├── README.md            # This file
└── .gitignore           # Git ignore rules
```

## Dependencies

- `yt-dlp`: YouTube video downloading
- `openai-whisper`: Audio transcription
- `moviepy`: Video editing and processing
- `google-generativeai`: Gemini AI API
- `torch`: Deep learning (Whisper dependency)
- `PIL`: Image processing (MoviePy dependency)

## Author / Resources

Si este código te ha servido, profundizar en la lógica detrás de la IA es lo que te diferenciará como ingeniero. Echa un vistazo a mis libros:

- 📖 Explora la Inteligencia Artificial: https://amzn.eu/d/dSwYhue
- 💻 Programar con Inteligencia Artificial: https://amzn.eu/d/eK4f73N
- Canal de YouTube: https://www.youtube.com/@jokioki?sub_confirmation=1


## License

MIT License - feel free to use and modify for your projects.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Tips for Best Results

1. **Choose videos with clear audio** - Whisper works best with clean speech
2. **Look for moments with strong reactions** - Gemini identifies these as viral potential
3. **Keep segments 30-60 seconds** - Ideal for Shorts attention spans
4. **Ensure good lighting and clear visuals** - Important for vertical format
5. **Test different subtitle styles** - Adjust colors and fonts for your brand
