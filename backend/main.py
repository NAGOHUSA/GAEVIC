from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="Houston County Eviction System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CaseData(BaseModel):
    landlord_name: str
    property_address: str
    tenant_name: str
    rent_amount: float
    reason: str
    notice_served_date: str
    # ... other fields

@app.post("/api/cases")
async def create_case(case_data: CaseData):
    """Create new eviction case"""
    # 1. Validate Houston County requirements
    # 2. Check SCRA
    # 3. Generate case ID
    # 4. Trigger document generation
    # 5. Return case information
    
    case_id = generate_case_id()
    
    # Trigger GitHub Actions workflow
    trigger_document_generation(case_id, case_data.dict())
    
    return {
        "case_id": case_id,
        "status": "documents_generating",
        "next_steps": ["review_documents", "pay_filing_fee"]
    }

@app.get("/api/cases/{case_id}/documents")
async def get_documents(case_id: str):
    """Get generated documents for case"""
    return {
        "documents": [
            {"name": "Eviction Notice", "url": f"/documents/{case_id}/notice.pdf"},
            {"name": "Affidavit", "url": f"/documents/{case_id}/affidavit.pdf"},
            {"name": "Dispossessory Warrant", "url": f"/documents/{case_id}/warrant.pdf"}
        ]
    }

@app.post("/api/cases/{case_id}/file")
async def file_with_court(case_id: str):
    """Submit case to Houston County Magistrate Court"""
    # Integrate with nCourt or direct e-filing
    return {"status": "filed", "confirmation": "HOU-2024-12345"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
