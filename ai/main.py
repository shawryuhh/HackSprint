import os
import math
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

app = FastAPI(title="ReliefMesh AI/ML Engine - Global & Pan-India Multilingual Intelligence Layer")

# ==========================================
# HEALTH CHECK & SYSTEM DIAGNOSTICS
# ==========================================
@app.get("/ai/health")
async def health_check():
    api_key_configured = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    return {
        "status": "healthy",
        "service": "ReliefMesh AI Engine",
        "model": "gemini-3.6-flash",
        "api_key_configured": api_key_configured
    }

# ==========================================
# MOCK ENDPOINT (System Contract Placeholder)
# ==========================================
@app.post("/ai/analyze-incident")
async def analyze_incident():
    return {
        "incident_id": "INC-1042",
        "priority_score": 94,
        "confidence": 0.91,
        "recommended_resources": ["AMB-02", "RESCUE-01"],
        "reason": "Medical emergency involving a vulnerable person",
        "approval_required": True
    }

# ==========================================
# PIPELINE 1: LLM Extraction (Global & Pan-India Multilingual Ready)
# ==========================================
class ExtractedIncident(BaseModel):
    location: str = Field(description="Specific location or building named in text (normalized to English)")
    incident_type: str = Field(description="e.g. flood_rescue, building_collapse, medical, fire, supply")
    people_affected: int = Field(description="Estimated count of people needing help")
    vulnerable_groups: list[str] = Field(description="e.g. ['elderly', 'children', 'disabled']")
    medical_urgency: bool = Field(description="True if medical assistance is explicitly required")
    severity_score: int = Field(description="Severity score from 1 (low) to 5 (critical)")
    time_sensitivity_hours: float = Field(description="Estimated hours before situation becomes critical or fatal")
    environmental_threat: bool = Field(description="True if active fire, rapid flooding, or structural collapse is occurring")
    confidence_score: float = Field(description="AI extraction confidence score between 0.0 and 1.0")

class ReportRequest(BaseModel):
    text: str = Field(description="Raw unstructured emergency report text in any global or regional language/script")

@app.post("/ai/extract-incident", response_model=ExtractedIncident)
async def extract_incident(report: ReportRequest):
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", temperature=0)
        structured_llm = llm.with_structured_output(ExtractedIncident)

        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are an expert emergency crisis dispatcher AI. Extract structured incident data from unstructured emergency reports. "
                "You are fully fluent in English, regional Hinglish, Gen Z slang/shorthand, major Indian regional languages "
                "(Hindi, Kannada, Tamil, Telugu, Malayalam, Bengali, Marathi, Gujarati, Punjabi, Odia, etc.), "
                "and major global foreign languages (such as Spanish, French, Arabic, Mandarin, German, Japanese, Russian, etc. in any script or transliteration). "
                "Regardless of the input language or script, translate and normalize all extracted details accurately into standard English JSON fields, "
                "estimate time sensitivity in hours, evaluate environmental threats, and rate your parsing confidence from 0.0 to 1.0."
            )),
            ("human", "{text}")
        ])

        chain = prompt | structured_llm
        result = chain.invoke({"text": report.text})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# PIPELINE 2: Advanced Enterprise Scoring Engine
# ==========================================
class AdvancedScoreRequest(BaseModel):
    location: str
    incident_type: str
    people_affected: int
    vulnerable_groups: list[str]
    medical_urgency: bool
    severity_score: int
    environmental_threat: bool
    time_sensitivity_hours: float
    confidence_score: float = 1.0

class AdvancedPriorityResponse(BaseModel):
    priority_score: int
    risk_level: str
    requires_human_review: bool
    scoring_breakdown: dict

CRITICAL_INCIDENT_TYPES = {"building_collapse", "dam_breach", "active_fire", "hazmat_leak"}

@app.post("/ai/score-incident", response_model=AdvancedPriorityResponse)
async def score_incident(incident: AdvancedScoreRequest):
    severity_points = (incident.severity_score / 5.0) * 35
    medical_points = 25 if incident.medical_urgency else 0
    vulnerable_points = min(len(incident.vulnerable_groups) * 7.5, 15)
    env_points = 10 if incident.environmental_threat else 0
    
    time_points = round(10 * math.exp(-0.35 * max(0.0, incident.time_sensitivity_hours)), 1)
    time_points = max(time_points, 1.0)
    
    if incident.people_affected > 1:
        scale_points = min(round(math.log10(incident.people_affected) * 5, 1), 10.0)
    else:
        scale_points = 0.0

    raw_total = severity_points + medical_points + vulnerable_points + env_points + time_points + scale_points
    
    requires_review = incident.confidence_score < 0.75
    is_critical_type = incident.incident_type.lower() in CRITICAL_INCIDENT_TYPES
    
    if is_critical_type:
        final_score = max(raw_total, 85)
    else:
        final_score = raw_total

    if incident.confidence_score < 0.6:
        final_score *= 0.85

    final_score = int(round(min(max(final_score, 0), 100)))
    
    if final_score >= 80:
        risk_level = "Critical"
    elif final_score >= 60:
        risk_level = "High"
    elif final_score >= 40:
        risk_level = "Medium"
    else:
        risk_level = "Low"
        
    return {
        "priority_score": final_score,
        "risk_level": risk_level,
        "requires_human_review": requires_review,
        "scoring_breakdown": {
            "severity_points": round(severity_points, 1),
            "medical_points": medical_points,
            "vulnerable_points": round(vulnerable_points, 1),
            "env_points": env_points,
            "time_points": time_points,
            "scale_points": scale_points,
            "confidence_score": incident.confidence_score,
            "critical_type_override": is_critical_type
        }
    }

# ==========================================
# PIPELINE 3: Semantic Deduplication Engine
# ==========================================
class ActiveIncidentSummary(BaseModel):
    incident_id: str
    location: str
    incident_type: str
    summary_text: str

class DeduplicationRequest(BaseModel):
    new_report_text: str
    active_incidents: List[ActiveIncidentSummary]

class DeduplicationResponse(BaseModel):
    is_duplicate: bool
    matched_incident_id: str | None = Field(description="ID of the active incident if matched, otherwise null")
    similarity_reason: str = Field(description="Explanation of why it is or isn't a duplicate")

@app.post("/ai/deduplicate-incident", response_model=DeduplicationResponse)
async def deduplicate_incident(payload: DeduplicationRequest):
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", temperature=0)
        structured_llm = llm.with_structured_output(DeduplicationResponse)

        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are an expert crisis data deduplication engine. Compare a new incoming emergency report against a list of currently active incidents. "
                "The reports may come in any regional, Indian, or global foreign language or script. "
                "Determine if the new report describes the exact same physical event/emergency already tracked in the active list, "
                "even if written in a completely different foreign language or script. "
                "Return whether it is a duplicate, the matching incident ID, and a clear reason."
            )),
            ("human", "New Report:\n{new_report}\n\nActive Incidents List:\n{active_list}")
        ])

        chain = prompt | structured_llm
        result = chain.invoke({
            "new_report": payload.new_report_text,
            "active_list": [inc.model_dump() for inc in payload.active_incidents]
        })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))