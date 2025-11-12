import speech_recognition as sr
import time
import queue
import threading
import os
from datetime import datetime, timedelta

# Konfigurasi model
MODEL_WHISPER = "medium"

# Konfigurasi audio
ENERGY_THRESHOLD = 300  # Lebih rendah agar lebih sensitif
DYNAMIC_ENERGY_THRESHOLD = True
PAUSE_THRESHOLD = 0.8
PHRASE_TIME_LIMIT = 10

class RealtimeTranscriber:
    def __init__(self):
        self.transcriptions = []
        self.audio_queue = queue.Queue()
        self.processing_queue = queue.Queue()
        self.is_recording = False
        self.start_time = None
        self.chunk_count = 0
        self.processing_thread = None
        self.lock = threading.Lock()
        
    def format_timestamp(self, seconds):
        """Format detik ke format HH:MM:SS,mmm"""
        td = timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        milliseconds = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
    
    def audio_callback(self, recognizer, audio):
        """Callback saat audio terdeteksi"""
        if self.is_recording:
            timestamp = time.time() - self.start_time
            self.chunk_count += 1
            self.audio_queue.put((audio, timestamp, self.chunk_count))
            print(f"\r🔴 Merekam... (Potongan #{self.chunk_count})", end="", flush=True)
    
    def process_audio_worker(self, recognizer):
        """Worker thread untuk memproses audio secara real-time"""
        while self.is_recording or not self.audio_queue.empty():
            try:
                # Ambil audio dari queue dengan timeout
                audio, timestamp, chunk_num = self.audio_queue.get(timeout=1)
                
                # Proses transkripsi
                try:
                    text = recognizer.recognize_whisper(
                        audio,
                        model=MODEL_WHISPER,
                        language="id"
                    )
                    
                    text = text.strip()
                    if text:
                        formatted_time = self.format_timestamp(timestamp)
                        
                        with self.lock:
                            self.transcriptions.append({
                                'timestamp': formatted_time,
                                'text': text,
                                'chunk': chunk_num
                            })
                        
                        # Tampilkan real-time
                        print(f"\n\n{'='*60}")
                        print(f"Speaker  {formatted_time}")
                        print(f"{text}")
                        print(f"{'='*60}")
                        
                except sr.UnknownValueError:
                    # Audio tidak jelas, skip
                    pass
                except Exception as e:
                    print(f"\n⚠️ Error memproses chunk #{chunk_num}: {e}")
                
            except queue.Empty:
                continue
    
    def start_recording(self):
        """Mulai proses recording dan transcription"""
        # Setup recognizer
        r = sr.Recognizer()
        r.energy_threshold = ENERGY_THRESHOLD
        r.dynamic_energy_threshold = DYNAMIC_ENERGY_THRESHOLD
        r.pause_threshold = PAUSE_THRESHOLD
        
        # Setup microphone
        source = sr.Microphone(sample_rate=16000)
        
        # Reset state
        self.transcriptions = []
        self.chunk_count = 0
        self.is_recording = True
        self.start_time = time.time()
        
        # Mulai processing thread
        self.processing_thread = threading.Thread(
            target=self.process_audio_worker,
            args=(r,),
            daemon=True
        )
        self.processing_thread.start()
        
        # Mulai listening di background
        stop_listening = r.listen_in_background(
            source,
            self.audio_callback,
            phrase_time_limit=PHRASE_TIME_LIMIT
        )
        
        print("="*60)
        print("🎙️  REAL-TIME TRANSCRIPTION - BAHASA INDONESIA")
        print("="*60)
        print("💡 Tips:")
        print("   - Berbicara dengan jelas dan tidak terlalu cepat")
        print("   - Hasil akan muncul secara real-time di bawah")
        print("\n⏸️  Tekan [ENTER] untuk berhenti")
        print("="*60)
        
        try:
            # Tunggu user menekan ENTER
            input()
            
            print("\n\n🛑 Menghentikan recording...")
            self.is_recording = False
            
            # Hentikan listening
            stop_listening(wait_for_stop=True)
            
            # Tunggu processing thread selesai
            print("⏳ Menunggu proses transkripsi terakhir...")
            self.processing_thread.join(timeout=30)
            
            # Tampilkan ringkasan
            self.show_summary()
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Program dihentikan paksa.")
            self.is_recording = False
            stop_listening(wait_for_stop=False)
    
    def show_summary(self):
        """Tampilkan ringkasan transkripsi lengkap"""
        print("\n\n" + "="*60)
        print("✅ TRANSKRIPSI SELESAI")
        print("="*60)
        print(f"📈 Statistik:")
        print(f"   - Total potongan: {self.chunk_count}")
        print(f"   - Berhasil ditranskripsi: {len(self.transcriptions)}")
        print(f"   - Durasi total: {self.format_timestamp(time.time() - self.start_time)}")
        
        if self.transcriptions:
            print("\n" + "="*60)
            print("📝 TRANSKRIP LENGKAP")
            print("="*60 + "\n")
            
            for item in self.transcriptions:
                print(f"Speaker  {item['timestamp']}")
                print(f"{item['text']}")
                print()
            
            print("-"*60)
            
            # Gabungan teks tanpa timestamp
            full_text = " ".join([item['text'] for item in self.transcriptions])
            
            print("\n📄 TEKS LENGKAP (Tanpa Timestamp):")
            print("-"*60)
            print(full_text)
            print("-"*60)
            
            # Opsi simpan
            print("\n")
            save_option = input("💾 Simpan hasil ke file? (y/n): ").lower()
            if save_option == 'y':
                self.save_to_file(full_text)
        else:
            print("\n⚠️  Tidak ada transkripsi yang berhasil.")
    
    def save_to_file(self, full_text):
        """Simpan hasil ke file"""
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Simpan versi dengan timestamp
        filename_detailed = f"transkripsi_detail_{timestamp_str}.txt"
        with open(filename_detailed, 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write("TRANSKRIPSI DENGAN TIMESTAMP\n")
            f.write("="*60 + "\n\n")
            for item in self.transcriptions:
                f.write(f"Speaker  {item['timestamp']}\n")
                f.write(f"{item['text']}\n\n")
        
        # Simpan versi plain text
        filename_plain = f"transkripsi_plain_{timestamp_str}.txt"
        with open(filename_plain, 'w', encoding='utf-8') as f:
            f.write(full_text)
        
        print(f"✅ File tersimpan:")
        print(f"   - Detail: {filename_detailed}")
        print(f"   - Plain:  {filename_plain}")

def main():
    # Cek Whisper
    try:
        import whisper
        print("✅ Whisper terdeteksi\n")
    except ImportError:
        print("❌ ERROR: Package 'openai-whisper' tidak terinstall")
        print("   Install dengan: pip install openai-whisper")
        exit(1)
    
    # Mulai transcriber
    transcriber = RealtimeTranscriber()
    transcriber.start_recording()

if __name__ == "__main__":
    main()