# app_fixed_v2.py
import os
import tempfile
import time
import json
import wave
import multiprocessing as mp

import sounddevice as sd
import soundfile as sf
from vosk import Model, KaldiRecognizer

import pyttsx3

MODEL_PATH = "model"
SAMPLE_RATE = 16000
CHANNELS = 1
DURATION = 5

# Vosk model (tek kez yükle)
if not os.path.exists(MODEL_PATH):
     print("Vosk model bulunamadı. model klasörünü MODEL_PATH içine koy.")
     raise SystemExit(1)
model = Model(MODEL_PATH)

def record_wav(duration=DURATION, filename=None):
     if filename is None:
          fd, filename = tempfile.mkstemp(suffix=".wav")
          os.close(fd)
     print(f"Kayıt başlıyor ({duration} s) — konuşun...")
     recording = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16')
     sd.wait()
     sf.write(filename, recording, SAMPLE_RATE, subtype='PCM_16')
     print("Kayıt tamamlandı ->", filename)
     return filename

def transcribe_wav(fname):
     wf = wave.open(fname, "rb")
     rec = KaldiRecognizer(model, SAMPLE_RATE)
     rec.SetWords(True)
     text = ""
     while True:
          data = wf.readframes(4000)
          if len(data) == 0:
               break
          if rec.AcceptWaveform(data):
               res = json.loads(rec.Result())
               text += " " + res.get("text", "")
     res = json.loads(rec.FinalResult())
     text += " " + res.get("text", "")
     return text.strip()

# ---------- Anlık TTS: her çağrıda yeni engine yarat (daha güvenli) ----------
def tts_speak_immediate_local(text):
     """Her çağrıda yeni pyttsx3 engine oluşturur, konuşur ve kapatır.
       Ayrıca sounddevice kaynaklarını serbest bırakmak için sd.stop() çağır."""
     if not text:
          return
     try:
          # kayıt sonrası audio cihaz çakışmasını önlemek için stop
          try:
               sd.stop()
          except Exception:
               pass
          # Yeni engine yarat
          engine = pyttsx3.init()
          engine.setProperty("rate", 160)
          engine.say(text)
          engine.runAndWait()
     except Exception as e:
          print("TTS hata:", e)
     finally:
          try:
               engine.stop()
          except Exception:
               pass
          time.sleep(0.05)

# ---------- WAV oluşturma (ayrı process) ----------
def _pyttsx3_save_worker(text, out_path):
     try:
          e = pyttsx3.init()
          e.save_to_file(text, out_path)
          e.runAndWait()
          e.stop()
     except Exception as ex:
          print("TTS save worker hata:", ex)

def tts_save_wav_in_process(text, out_path, timeout=12.0):
     p = mp.Process(target=_pyttsx3_save_worker, args=(text, out_path))
     p.start()
     p.join(timeout)
     if p.is_alive():
          p.terminate()
          p.join(0.2)
          raise RuntimeError("TTS save worker timeout, dosya oluşturulamadı.")
     if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
          raise RuntimeError("TTS WAV dosyası oluşturulamadı.")
     return out_path

# Akışlar
def stt_then_tts_flow():
     wav = record_wav(duration=DURATION)
     text = transcribe_wav(wav)
     print("STT sonucu:", text)
     if text:
          print("TTS olarak anında seslendiriliyor...")
          tts_speak_immediate_local(text)
     try:
          os.remove(wav)
     except:
          pass

def tts_then_stt_flow():
     user_text = input("TTS için yazı gir: ").strip()
     if not user_text:
          print("Boş metin.")
          return
     print("Anında seslendiriliyor...")
     tts_speak_immediate_local(user_text)

     do_roundtrip = input("TTS->STT (oluşturulan WAV'ı STT ile oku)? (e/h): ").strip().lower()
     if do_roundtrip == 'e':
          tmp = tempfile.mktemp(suffix=".wav")
          print("WAV oluşturuluyor (ayrı process)...")
          try:
               tts_save_wav_in_process(user_text, tmp, timeout=12.0)
               time.sleep(0.3)
               print("Oluşturulan WAV dosyasından STT yapılıyor...")
               text = transcribe_wav(tmp)
               print("STT sonucu (TTS->STT):", text)
          except Exception as ex:
               print("WAV oluşturma veya STT sırasında hata:", ex)
          finally:
               try:
                    os.remove(tmp)
               except:
                    pass

def main_menu():
     print("Seçenekler:\n1 - STT (kayıt) -> TTS (seslendir)\n2 - TTS (yazı) -> (anında konuş) + isteğe bağlı TTS->STT\nq - çık")
     while True:
          c = input("Seçiminiz (1/2/q): ").strip().lower()
          if c == '1':
               stt_then_tts_flow()
          elif c == '2':
               tts_then_stt_flow()
          elif c == 'q':
               print("Çıkılıyor.")
               break
          else:
               print("Geçersiz seçim.")

if __name__ == "__main__":
     mp.set_start_method('spawn', force=True)
     main_menu()
