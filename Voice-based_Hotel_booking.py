from fastapi import FastAPI, HTTPException, Form
from twilio.rest import Client
import speech_recognition as sr
from sentence_transformers import SentenceTransformer
import requests
import io
import time
from pinecone import Pinecone
from pydub import AudioSegment

app = FastAPI()

# Twilio credentials
ACCOUNT_SID = "AC98646da27b8b6151124187ba0f631135"
AUTH_TOKEN = "eea159c7e76c120e61abd64bbaab8388"
TWILIO_PHONE_NUMBER = "+19563005082"

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Initialize Pinecone
pc = Pinecone(api_key="pcsk_3WgoJJ_Nj75bAzAVqNQcLj8s5ByuxAudz9KtWaTiXP7TttE14bbcYvuqJrnNSPnuNgnDWf")

# Connect to an index
index = pc.Index("test")

hotel_index = pc.Index("hotels")

# Load SentenceTransformer model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Predefined list of hotels
def store_hotels():
    hotels = [
        {"id": "hotel_101", "name": "Sunset Resort"},
        {"id": "hotel_102", "name": "Mountain Lodge"},
        {"id": "hotel_103", "name": "Grand Palace Hotel"},
        {"id": "hotel_104", "name": "Oceanview Suites"}
    ]
    # Check if hotels already exist
    existing_hotels = hotel_index.describe_index_stats()
    if existing_hotels["total_vector_count"] == 0:
        vectors = [(hotel["id"], model.encode(hotel["name"]).tolist(), {"name": hotel["name"]}) for hotel in hotels]
        hotel_index.upsert(vectors)


store_hotels()  # Ensure hotels are stored
#     vectors = [(hotel["id"], model.encode(hotel["name"]).tolist(), {"name": hotel["name"]}) for hotel in hotels]
#     hotel_index.upsert(vectors)
# store_hotels()

# Function to fetch hotel names from Pinecone
# Function to fetch hotel names from Pinecone
def get_hotels_from_pinecone():
    try:
        results = hotel_index.query(vector=[0] * 384, top_k=10, include_metadata=True)

        hotels = [match["metadata"]["name"] for match in results["matches"] if
                  "metadata" in match and "name" in match["metadata"]]

        if not hotels:
            return ["No hotels available."]
        return hotels
    except Exception as e:
        print(f"Error fetching hotels from Pinecone: {e}")
        return ["No hotels available."]


def preprocess_audio(audio_bytes):
    """Preprocess audio to improve recognition accuracy."""
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav")
        # Normalize volume and remove silence
        normalized_audio = audio.normalize()
        output = io.BytesIO()
        normalized_audio.export(output, format="wav")
        return output.getvalue()
    except Exception as e:
        print(f"Error during audio preprocessing: {e}")
        raise HTTPException(status_code=500, detail="Error during audio preprocessing.")


@app.post("/make_call_and_process/")
async def make_call_and_process(to: str = Form(...)):
    try:
        # Fetch hotels from Pinecone
        hotels_list = get_hotels_from_pinecone()
        hotels_text = ", ".join(hotels_list) if hotels_list else "No hotels available."
        # Step 1: Make the call
        call = client.calls.create(
            to=to,
            from_=TWILIO_PHONE_NUMBER,
            twiml=f'''
            <Response>
                <Say>Hello! Welcome to our services. Please say your name, mobile number, and email after the beep.</Say>
                <Record maxLength="40" playBeep="true" transcribe="true" />

                <Say>Now, please tell us which hotel you would like to book a table at.</Say> 
                <Pause length="1" />
                <Say>Here are the available hotels: {hotels_text}.</Say>
                <Say>Please say the name of the hotel you would like to book after the beep.</Say>
                <Record maxLength="30" playBeep="true" transcribe="true"  />

                <Say>On which date and at what time would you like to book the table?</Say>
                <Record maxLength="30" playBeep="true" transcribe="true"  />

                <Say>Thank you for booking a table. We will send you an email. We look forward to your visit!</Say>
            </Response>
            '''
        )

        print(f"Call initiated with SID: {call.sid}. Waiting for the recording...")

        # Step 2: Poll for the recording
        recording = None
        max_attempts = 30  # Increased max attempts
        wait_time = 10  # Increased wait time
        attempt = 0

        while attempt < max_attempts:
            recordings = client.recordings.list(call_sid=call.sid, limit=3)
            if len(recordings) == 3:
                recording = recordings
                print(f"Recording found: {[rec.sid for rec in recording]}")
                break
            attempt += 1
            time.sleep(wait_time)

        if not recording:
            raise HTTPException(status_code=400, detail="Recording not found for this call.")

        # Step 3: Fetch recordings
        recording_urls = [
            f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/Recordings/{rec.sid}.wav"
            for rec in recording
        ]

        audio_responses = []
        for url in recording_urls:
            attempt = 0
            while attempt < max_attempts:
                audio_response = requests.get(url, auth=(ACCOUNT_SID, AUTH_TOKEN))
                if audio_response.status_code == 200:
                    audio_responses.append(audio_response)
                    break
                attempt += 1
                time.sleep(wait_time)

            if audio_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Recording not fully processed or unavailable.")

        # Step 4: Convert speech to text
        recognizer = sr.Recognizer()
        recognized_texts = []

        for i, audio_response in enumerate(audio_responses):
            preprocessed_audio = preprocess_audio(audio_response.content)
            audio_data = io.BytesIO(preprocessed_audio)
            try:
                with sr.AudioFile(audio_data) as source:
                    recognizer.adjust_for_ambient_noise(source, duration=1.0)
                    audio = recognizer.record(source)

                try:
                    recognized_text = recognizer.recognize_google(audio)
                    print(f"Recognized Text for Recording {i + 1}: {recognized_text}")
                except sr.UnknownValueError:
                    recognized_text = "Speech could not be recognized."
                except sr.RequestError as e:
                    recognized_text = f"Speech recognition error: {e}"

                recognized_texts.append(recognized_text)

            except Exception as e:
                print(f"Error during speech recognition: {e}")
                raise HTTPException(status_code=500, detail="Error during speech recognition.")

        print(f"Recognized Texts: {recognized_texts}")

        # Validate recognized texts
        if not all(recognized_texts):
            raise HTTPException(status_code=400, detail="One or more recordings could not be transcribed.")

        # Step 5: Convert text to vectors
        user_info_vector = model.encode(recognized_texts[2]).tolist()
        hotel_vector = model.encode(recognized_texts[1]).tolist()
        date_time_vector = model.encode(recognized_texts[0]).tolist()

        # Step 6: Store in Pinecone
        index.upsert([
            ("user_info_" + call.sid, user_info_vector, {"text": recognized_texts[2]}),
            ("hotel_" + call.sid, hotel_vector, {"text": recognized_texts[1]}),
            ("date_time_" + call.sid, date_time_vector, {"text": recognized_texts[0]})
        ])

        return {
            "message": "Booking successful",
            "user_info": recognized_texts[2],
            "hotel": recognized_texts[1],
            "date_time": recognized_texts[0]
        }

    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))