from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import whisper, uuid, os, pysrt, requests

app = FastAPI()
app.mount("/", StaticFiles(directory="static", html=True), name="static")

model = whisper.load_model("base")

QURAN_TEXT = {}
try:
    response = requests.get("https://api.quran.sutanlab.id/surah")
    for surah in response.json()["data"]:
        sid = surah["number"]
        res = requests.get(f"https://api.quran.sutanlab.id/surah/{sid}")
        for verse in res.json()["data"]["verses"]:
            text = verse["text"]["arab"]
            QURAN_TEXT[text.replace(" ", "")] = f"{sid}:{verse['number']['inSurah']}"
except:
    QURAN_TEXT = {}

@app.post("/upload/")
async def upload(file: UploadFile = File(...)):
    temp_file = f"temp_{uuid.uuid4().hex}.mp3"
    with open(temp_file, "wb") as f:
        f.write(await file.read())

    result = model.transcribe(temp_file, language="ar")
    segments = result["segments"]

    srt_file = temp_file.replace(".mp3", ".srt")
    subs = pysrt.SubRipFile()

    for i, seg in enumerate(segments):
        cleaned = seg["text"].replace(" ", "")
        match = None
        label = seg["text"]
        for k, ayat in QURAN_TEXT.items():
            if k in cleaned:
                match = ayat
                surah_num, ayah_num = map(int, ayat.split(":"))
                trans_url = f"https://api.quran.sutanlab.id/surah/{surah_num}/{ayah_num}?lang=en"
                try:
                    res = requests.get(trans_url).json()
                    translation = res["data"]["translation"]["en"]
                    label = f"{seg['text']} [{match}]\n{translation}"
                except:
                    label = f"{seg['text']} [{match}]"
                break

        subs.append(pysrt.SubRipItem(
            index=i + 1,
            start=pysrt.SubRipTime(seconds=seg["start"]),
            end=pysrt.SubRipTime(seconds=seg["end"]),
            text=label
        ))

    subs.save(srt_file)
    os.remove(temp_file)
    return FileResponse(srt_file, filename="subtitle.srt", media_type="application/x-subrip")
