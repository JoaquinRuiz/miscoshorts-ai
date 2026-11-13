import yt_dlp
from moviepy import VideoFileClip
import os
import warnings
import sys

# own modules
# AI backend: "gemini" (default) or "openai" (any OpenAI-compatible API: Ollama, LM Studio, llama.cpp...).
backend = os.getenv("CEREBRO_BACKEND", "gemini").lower()
if backend == "gemini":
    import cerebro_gemini as cerebro
elif backend == "openai":
    import cerebro_openai as cerebro
else:
    raise ValueError(f"Unsupported CEREBRO_BACKEND: {backend}")
import subtitulos
import subtitulos_whisper

warnings.filterwarnings("ignore")

# URL can be passed as a command‑line argument:
#   python3 maker.py "https://youtube.com/..."
URL_VIDEO = sys.argv[1] if len(sys.argv) > 1 else "TU_URL_DE_VIDEO_AQUI"
# Set USE_WHISPER_API=true to transcribe with a remote whisper-server instead of local Whisper.
USE_WHISPER_API = os.getenv("USE_WHISPER_API", "false").lower() == "true"
NOMBRE_SALIDA = "short_con_subs.mp4"

def descargar_video(url):
    print(f"📥 Descargando video: {url}...")
    ydl_opts = {'format': 'best[ext=mp4]', 'outtmpl': 'video_temp.%(ext)s', 'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return "video_temp.mp4"

def parsear_respuesta_gemini(texto):
    """Extrae los datos limpios de la respuesta de texto de Gemini"""
    datos = {}
    lines = texto.split('\n')
    for line in lines:
        if "TITULO:" in line: datos['titulo'] = line.split("TITULO:")[1].strip()
        if "INICIO:" in line: datos['inicio'] = float(line.split("INICIO:")[1].strip())
        if "FIN:" in line: datos['fin'] = float(line.split("FIN:")[1].strip())
        if "RAZON:" in line: datos['razon'] = line.split("RAZON:")[1].strip()
    return datos

def main():
    video_path = descargar_video(URL_VIDEO)
    
    print("🔍 Transcribiendo audio para obtener tiempos...")
    resultado = subtitulos_whisper.transcribe_and_save(video_path, URL_VIDEO, use_api=USE_WHISPER_API)

    analisis = cerebro.encontrar_clip_viral(resultado['segments'])
    clip_data = parsear_respuesta_gemini(analisis)

    print(f"🤖 PROPUESTA DE SHORT:")
    print(f"📌 Título: {clip_data.get('titulo')}")
    print(f"⏱️ Tiempo: {clip_data.get('inicio')}s --> {clip_data.get('fin')}s")
    print(f"💡 Razón: {clip_data.get('razon')}")
    confirmacion = input("¿Te mola? Escribe 's' para crearlo, o introduce nuevos tiempos (ej: 120-140): ")
    
    start = 0
    end = 0
    if confirmacion.lower() == 's':
        start = clip_data['inicio']
        end = clip_data['fin']
    elif '-' in confirmacion:
        partes = confirmacion.split('-')
        start = float(partes[0])
        end = float(partes[1])
    else:
        print("Cancelado.")
        return

    print(f"🚀 Cocinando el Short ({start}s a {end}s)...")
    clip = VideoFileClip(video_path).subclipped(start, end)

    w, h = clip.size
    new_width = h * (9/16)
    clip_vertical = clip.cropped(x1=w/2 - new_width/2, y1=0, x2=w/2 + new_width/2, y2=h)

    clip_final = subtitulos.generar_subtitulos(clip_vertical, resultado['segments'], start)
    clip_final.write_videofile(NOMBRE_SALIDA, 
                               codec='libx264', 
                               audio_codec='aac', 
                               fps=24,
                               threads=4)
    
    clip.close()
    os.remove(video_path)
    print(f"🎉 ¡Video listo: {NOMBRE_SALIDA}!")

if __name__ == "__main__":
    main()
