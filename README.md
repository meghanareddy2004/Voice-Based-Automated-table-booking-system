# Voice-Based-Automated-table-booking-system 

This repository provides a FastAPI application that integrates Twilio for voice call processing, Google's Speech-to-Text API for transcription, and Pinecone for vector database storage. The application is designed to handle user interactions over voice, convert speech into text, and store relevant booking details as vector embeddings.  

## Setup Instructions 

### 1. Install Dependencies  
Clone the repository and install the required dependencies:  

pip install fastapi twilio speechrecognition sentence-transformers requests pydub pinecone-client uvicorn


Ensure all necessary Python packages are installed before running the application.  

### 2. Twilio Setup 
- Sign up for Twilio and generate a **Twilio phone number**.  
- Obtain your **Twilio Account SID** and **Auth Token** from the Twilio Console.  
- Add the Twilio credentials to your FastAPI application to enable voice call handling.  

### 3. Pinecone Setup  
- Sign up on [Pinecone](https://www.pinecone.io/) and generate an **API key**.  
- Create **two indexes** in Pinecone to store vectorized speech data.  
- Configure your Pinecone environment by adding the API key and index names to your FastAPI application.  

### 4. Running the FastAPI Application  
Start the FastAPI server using PyCharm or manually with:  

uvicorn main:app --host 0.0.0.0 --port 8000

### 5. Expose API Using Ngrok 
To make the local API accessible over the internet, use **ngrok**:  

1. Download and install [ngrok](https://ngrok.com/).  
2. Run ngrok to expose your FastAPI service:  

ngrok http 8000

3.Copy the public ngrok URL and configure it in your Twilio console under Webhook settings.


### 6. Testing the API
Open a browser and navigate to your FastAPI endpoint using the PyCharm-hosted URL or the ngrok public URL.
Validate that the API is running successfully.

3. Copy the public **ngrok URL** and configure it in your Twilio console under **Webhook settings**.  

### **6. Testing the API**  
- Open a browser and navigate to your FastAPI endpoint using the **PyCharm-hosted URL** or the **ngrok public URL**.  
- Validate that the API is running successfully.  

Now, Twilio will route incoming calls to your FastAPI application, process speech-to-text conversion, and store data in Pinecone. 🚀
