import azure.cognitiveservices.speech as speechsdk
import time

# Azure credentials
speech_key = "DSKcmp4mgQc1MqiN1cbPA7zOAxxZXTOFwyiedc7qElXLQPcgpXJxJQQJ99BDACGhslBXJ3w3AAAYACOGyDin"
service_region = "centralindia"  # e.g., "eastus"

# Initialize speech config
speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
speech_config.speech_synthesis_voice_name = "en-IN-AnanyaNeural"  # Use neural voice

# Set output format to PCM/WAV for speaker playback
speech_config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
)

# Set up synthesizer to play audio through default speaker
audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

# Text to synthesize
text = "After taking various diplomatic actions in the aftermath of the deadly terror attack in Kashmir’s Pahalgam, the Narendra Modi government has directed the Indian military to develop a robust strategy targeting Pakistan’s terrorist groups/assets and their military backers in the neighbouring country. A key Indian government functionary, who did not wish to be named, hinted that India’s response this time would be loud and clear. Prime Minister Narendra Modi has already issued a strong warning that “India will identify, track and punish every terrorist and their backers"

# Measure time
start_time = time.time()
result = synthesizer.speak_text_async(text).get()
end_time = time.time()

# Time taken
duration = end_time - start_time
print(f"Processing time for text-to-speech: {duration:.2f} seconds")

# Handle result
if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    print("Audio synthesis completed.")
    # Save audio if needed
    with open("output.mp3", "wb") as f:
        f.write(result.audio_data)
else:
    print("Synthesis failed:", result.error_details)
