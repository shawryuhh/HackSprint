# ReliefMesh AI Engine 🧠
**Lead AI/ML Engineer & Maintainer:** Arkin Sharma

## 🎯 Overview & My Role
The ReliefMesh AI Engine is a standalone intelligence microservice built to process, score, and route emergency crisis reports. 

My primary task in this project was to solve a critical bottleneck in disaster response: making sense of chaotic, unstructured data. During a crisis, reports come in across multiple regional languages, often containing slang or incomplete sentences. **I architected and developed this AI backend from the ground up** to ingest that raw text, extract structured operational data, calculate mathematical priority scores, and prevent duplicate dispatches.

## 🏗️ What I Built & How It Works

To achieve this, I engineered three core backend pipelines using FastAPI, Pydantic, and LangChain:

### 1. Multilingual LLM Extraction Pipeline
**The Problem:** Emergency reports are unstructured and multilingual, making them impossible for standard databases to parse.
**The Solution:** I integrated Google's `gemini-3.6-flash` model via LangChain. I engineered a highly specific system prompt that forces the LLM to act as a crisis dispatcher. It dynamically translates and normalizes inputs from any language (including regional Indian dialects and Hinglish) into a strictly typed Pydantic schema (`ExtractedIncident`). It accurately pulls the location, incident type, affected count, and environmental threats.

### 2. Advanced Priority Scoring Engine
**The Problem:** Dispatchers need to know *who* to help first when hundreds of reports flood in.
**The Solution:** Instead of relying on the LLM to guess a priority, I wrote a deterministic, pure-math scoring engine in Python. It calculates a priority score (0-100) based on weighted factors:
* **Severity & Vulnerability:** Scales linearly based on the presence of vulnerable groups (elderly, children).
* **Time Decay:** Uses an exponential decay function (`math.exp`) to aggressively prioritize highly time-sensitive reports.
* **Algorithmic Penalties:** Automatically applies an 85% penalty modifier if the LLM's extraction confidence score drops below 0.6, flagging it for human review.

### 3. Semantic Deduplication Engine
**The Problem:** Multiple people often report the exact same fire or flood, which wastes rescue resources.
**The Solution:** I built an endpoint that compares new incoming unstructured text against a live array of active incidents. By leveraging the LLM's semantic reasoning, it can identify if a new report in *Gujarati* describes the exact same physical event as an active report written in *English*, returning the matched ID and halting duplicate dispatch.

## 🚀 Tech Stack
* **Web Framework:** FastAPI, Uvicorn (Asynchronous API serving)
* **Data Validation:** Pydantic (Strict JSON contract enforcement)
* **AI/ML:** LangChain, Google Generative AI (Gemini 3.6 Flash)
* **Testing:** Pytest, HTTPX (Mocked contract testing)

## 🛠️ Setup & Installation

**1. Navigate to the AI service directory:**
`cd ai`

**2. Create and activate a virtual environment:**
`python -m venv venv`
`source venv/bin/activate` *(On Windows use `venv\Scripts\activate`)*

**3. Install dependencies:**
`pip install -r requirements.txt`

**4. Environment Variables:**
Create a `.env` file in the root of the `ai` directory and add your Google API key:
`GOOGLE_API_KEY=your_gemini_api_key_here`

## ⚡ Running the Server

Start the FastAPI development server:
`uvicorn main:app --reload`

The API will be available at `http://localhost:8000`. You can view the interactive Swagger UI and test the endpoints directly at `http://localhost:8000/docs`.

## 📡 API Reference

* `GET /ai/health` - Diagnostic endpoint to verify service uptime and API key configuration.
* `POST /ai/extract-incident` - Ingests raw text and returns a strictly typed JSON schema of the emergency.
* `POST /ai/score-incident` - Mathematical engine that calculates dispatch priority and risk levels.
* `POST /ai/deduplicate-incident` - Semantic matching engine to prevent duplicate resource allocation.

## 🧪 Testing

I implemented a comprehensive test suite to ensure mathematical boundaries and API contracts remain perfectly stable. Run the tests via:
`python -m pytest`