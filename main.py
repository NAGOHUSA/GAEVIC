from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import os
import uuid
from datetime import datetime
import shutil
from pathlib import Path

app = FastAPI(title="Houston County Eviction System")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup directories
BASE_DIR = Path(__file__).parent
CASES_DIR = BASE_DIR / "cases"
DATA_DIR = BASE_DIR / "data"
CASES_DB_FILE = DATA_DIR / "cases.json"

# Ensure directories exist
CASES_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class CaseSubmission(BaseModel):
    case_data: Dict[str, Any]
    signature_data: Optional[str] = None
    documents: Dict[str, str] = {}  # base64 encoded documents

@app.get("/")
async def home(request: Request):
    """Serve the main application"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard")
async def dashboard(request: Request):
    """Serve the dashboard"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.post("/api/submit-case")
async def submit_case(submission: CaseSubmission):
    """Submit a new eviction case"""
    try:
        # Generate case ID
        timestamp = int(datetime.now().timestamp())
        random_num = str(uuid.uuid4())[:8]
        case_id = f"HOU-{datetime.now().year}-{timestamp}-{random_num}"
        
        # Prepare case data
        case_data = submission.case_data
        case_data["case_id"] = case_id
        case_data["submitted_at"] = datetime.now().isoformat()
        case_data["status"] = "submitted"
        case_data["signature_data"] = submission.signature_data
        
        # Create case directory
        case_dir = CASES_DIR / case_id
        case_dir.mkdir(exist_ok=True)
        
        # Save case data
        case_json = case_dir / "case_data.json"
        with open(case_json, 'w') as f:
            json.dump(case_data, f, indent=2)
        
        # Save documents
        for doc_type, doc_base64 in submission.documents.items():
            # Decode and save PDF
            import base64
            pdf_data = base64.b64decode(doc_base64)
            doc_path = case_dir / f"{doc_type}.pdf"
            with open(doc_path, 'wb') as f:
                f.write(pdf_data)
        
        # Update database
        update_case_database(case_data)
        
        return {
            "success": True,
            "case_id": case_id,
            "message": "Case submitted successfully",
            "next_steps": "Your case is pending review. You will receive an email with further instructions."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Submission failed: {str(e)}")

@app.get("/api/cases/{case_id}")
async def get_case(case_id: str):
    """Get case details"""
    case_dir = CASES_DIR / case_id
    if not case_dir.exists():
        raise HTTPException(status_code=404, detail="Case not found")
    
    case_json = case_dir / "case_data.json"
    with open(case_json, 'r') as f:
        case_data = json.load(f)
    
    # Get list of documents
    documents = []
    for file_path in case_dir.glob("*.pdf"):
        documents.append({
            "name": file_path.stem.replace("_", " ").title(),
            "filename": file_path.name,
            "url": f"/api/cases/{case_id}/documents/{file_path.name}"
        })
    
    case_data["documents"] = documents
    return case_data

@app.get("/api/cases/{case_id}/documents/{filename}")
async def download_case_document(case_id: str, filename: str):
    """Download a case document"""
    file_path = CASES_DIR / case_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/pdf"
    )

@app.get("/api/cases/{case_id}/download-all")
async def download_all_documents(case_id: str):
    """Download all documents for a case as ZIP"""
    case_dir = CASES_DIR / case_id
    if not case_dir.exists():
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Create temporary ZIP file
    import tempfile
    import zipfile
    
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    
    with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in case_dir.iterdir():
            if file_path.is_file():
                zipf.write(file_path, file_path.name)
    
    return FileResponse(
        path=temp_zip.name,
        filename=f"{case_id}_documents.zip",
        media_type="application/zip"
    )

def update_case_database(case_data: Dict[str, Any]):
    """Update the cases database"""
    cases = []
    if CASES_DB_FILE.exists():
        with open(CASES_DB_FILE, 'r') as f:
            cases = json.load(f)
    
    # Add or update case
    existing_index = next((i for i, c in enumerate(cases) if c.get("case_id") == case_data["case_id"]), None)
    if existing_index is not None:
        cases[existing_index] = case_data
    else:
        cases.append(case_data)
    
    with open(CASES_DB_FILE, 'w') as f:
        json.dump(cases, f, indent=2)

@app.get("/api/dashboard/cases")
async def get_all_cases():
    """Get all cases for dashboard"""
    if not CASES_DB_FILE.exists():
        return {"cases": [], "count": 0}
    
    with open(CASES_DB_FILE, 'r') as f:
        cases = json.load(f)
    
    # Sort by submission date (newest first)
    cases.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
    
    return {"cases": cases, "count": len(cases)}

@app.post("/api/dashboard/cases/{case_id}/update-status")
async def update_case_status(case_id: str, status: str, notes: Optional[str] = None):
    """Update case status"""
    if not CASES_DB_FILE.exists():
        raise HTTPException(status_code=404, detail="Case database not found")
    
    with open(CASES_DB_FILE, 'r') as f:
        cases = json.load(f)
    
    case_index = next((i for i, c in enumerate(cases) if c.get("case_id") == case_id), None)
    if case_index is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Update status
    cases[case_index]["status"] = status
    cases[case_index]["updated_at"] = datetime.now().isoformat()
    
    if notes:
        cases[case_index]["admin_notes"] = notes
    
    # Also update the case directory
    case_dir = CASES_DIR / case_id
    if case_dir.exists():
        case_json = case_dir / "case_data.json"
        with open(case_json, 'r') as f:
            case_data = json.load(f)
        
        case_data["status"] = status
        case_data["updated_at"] = datetime.now().isoformat()
        
        if notes:
            case_data["admin_notes"] = notes
        
        with open(case_json, 'w') as f:
            json.dump(case_data, f, indent=2)
    
    # Save updated database
    with open(CASES_DB_FILE, 'w') as f:
        json.dump(cases, f, indent=2)
    
    return {"success": True, "case_id": case_id, "status": status}

@app.post("/api/dashboard/cases/{case_id}/assign-number")
async def assign_case_number(case_id: str, case_number: str, filing_date: Optional[str] = None):
    """Assign official court case number"""
    if not CASES_DB_FILE.exists():
        raise HTTPException(status_code=404, detail="Case database not found")
    
    with open(CASES_DB_FILE, 'r') as f:
        cases = json.load(f)
    
    case_index = next((i for i, c in enumerate(cases) if c.get("case_id") == case_id), None)
    if case_index is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Update with official case number
    cases[case_index]["official_case_number"] = case_number
    cases[case_index]["status"] = "filed"
    cases[case_index]["filing_date"] = filing_date or datetime.now().date().isoformat()
    cases[case_index]["assigned_at"] = datetime.now().isoformat()
    
    # Also update the case directory
    case_dir = CASES_DIR / case_id
    if case_dir.exists():
        case_json = case_dir / "case_data.json"
        with open(case_json, 'r') as f:
            case_data = json.load(f)
        
        case_data["official_case_number"] = case_number
        case_data["status"] = "filed"
        case_data["filing_date"] = filing_date or datetime.now().date().isoformat()
        case_data["assigned_at"] = datetime.now().isoformat()
        
        with open(case_json, 'w') as f:
            json.dump(case_data, f, indent=2)
    
    # Save updated database
    with open(CASES_DB_FILE, 'w') as f:
        json.dump(cases, f, indent=2)
    
    return {"success": True, "case_id": case_id, "official_case_number": case_number}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
