import sys
import os
import shutil
import subprocess
from TTS.api import TTS
from playsound import playsound
import torch  # Added for GPU check
import noisereduce as nr  # Added for noise reduction
import soundfile as sf   # Added for reading/writing audio files
import threading  # Added for threading
import queue      # Added for queue

torch.set_num_threads(8)  # Limit CPU threads; adjust based on your CPU

def check_espeak():
    common_paths = [
        r"C:\Program Files\eSpeak NG",
        r"C:\Program Files (x86)\eSpeak NG",
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            os.environ["PATH"] = path + os.pathsep + os.environ["PATH"]
            bin_path = os.path.join(path, "espeak-ng.exe")
            if os.path.exists(bin_path):
                try:
                    result = subprocess.run([bin_path, "--version"], capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"Espeak-ng version: {result.stdout.strip()}")
                        # Ensure that an 'espeak' backend is available
                        if not (shutil.which('espeak') or shutil.which('espeak-ng')):
                            # Create a temporary directory for the espeak copy
                            temp_dir = os.path.join(os.getcwd(), "tempbin")
                            os.makedirs(temp_dir, exist_ok=True)
                            dest_path = os.path.join(temp_dir, "espeak.exe")
                            try:
                                shutil.copy(bin_path, dest_path)
                                os.environ["PATH"] = temp_dir + os.pathsep + os.environ["PATH"]
                                print("Created copy of espeak-ng.exe as espeak.exe in tempbin directory")
                            except Exception as e:
                                print(f"Failed to copy espeak-ng.exe to create espeak.exe: {e}")
                        # Final check for either binary
                        if shutil.which('espeak') or shutil.which('espeak-ng'):
                            print("Espeak backend available.")
                            os.environ["ESPEAK_DATA_PATH"] = path
                            return
                except Exception as e:
                    print(f"Error running espeak-ng: {e}")
    
    print("Error: Working espeak backend not found")
    print("Please ensure you have:")
    print("1. Downloaded and installed espeak-ng from: https://github.com/espeak-ng/espeak-ng/releases")
    print("2. Added its installation directory (and its espeak-ng.exe) to your system PATH, or allow this script to create a copy as espeak.exe")
    print("3. Restarted your terminal/IDE after installation")
    print("\nCurrent PATH:")
    for p in os.environ["PATH"].split(os.pathsep):
        print(f"  - {p}")
    sys.exit(1)

# Call the check before TTS initialization
check_espeak()

use_gpu = False  # Force CPU usage

# Revert back to the preferred model (tacotron2-DDC)
model_name = "tts_models/en/ljspeech/tacotron2-DDC"  # switched back to tacotron2-DDC as preferred
print(f"Initializing TTS with model: {model_name}, GPU enabled: {use_gpu}")
tts = TTS(model_name, progress_bar=False, gpu=use_gpu)  # Updated TTS initialization with tacotron2-DDC
output_file = "output.wav"
# Select default speaker if model is multi-speaker
speaker = tts.speakers[0] if hasattr(tts, "speakers") and tts.speakers else None
if speaker:
    print(f"Using default speaker: {speaker}")

# Define the text with paragraphs separated by empty lines
full_text = """Hello, this is a test! What is times of India? The Times of India (TOI) is an Indian English-language daily newspaper and digital news media owned and managed by The Times Group. It is the fourth-largest newspaper in India by circulation and largest selling English-language daily in the world. It is the oldest English-language newspaper in India, and the second-oldest Indian newspaper still in circulation, with its first edition published in 1838.

What Happened to Ranveer Allahbadia case?
A Bench comprising Justices Surya Kant and N. Kotiswar Singh imposed stringent conditions, prohibiting Allahbadia and his associates from posting any content on social media until further orders. The court also directed him to surrender his passport to the police, effectively restraining him from leaving the country."""
paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]

audio_queue = queue.Queue()

def tts_worker():
    for i, para in enumerate(paragraphs):
        file_name = f"output_section_{i}.wav"
        print(f"Generating audio for paragraph {i+1}...")
        # If the paragraph is a question, try using an alternative speaker (if available)
        if "?" in para:
                chosen_speaker = speaker
        else:
            chosen_speaker = speaker
        tts.tts_to_file(para, speaker=chosen_speaker, speed=1.2, file_path=file_name)
        audio_queue.put(file_name)
    audio_queue.put("STOP")  # Signal completion

def playback_worker():
    while True:
        file_name = audio_queue.get()
        if file_name == "STOP":
            break
        print(f"Playing generated audio from {file_name}")
        try:
            playsound(file_name)
        except Exception as audio_error:
            print(f"Error playing audio from {file_name}: {str(audio_error)}")
            sys.exit(1)

# Start concurrent processing: generate and play audio in a pipelined fashion
tts_thread = threading.Thread(target=tts_worker)
playback_thread = threading.Thread(target=playback_worker)

tts_thread.start()
playback_thread.start()

tts_thread.join()
playback_thread.join()