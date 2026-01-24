from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import zipfile
import io

app = FastAPI(title="Eviction Case Dashboard API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Mock database (in production, use real database)
CASES_DB_FILE = "data/cases.json"
CASES_DIR = "cases"

# Ensure directories exist
Path("data").mkdir(exist_ok=True)
Path(CASES_DIR).mkdir(exist_ok=True)

class CaseData(BaseModel):
    case_id: str
    landlord_name: str
    landlord_email: str
    landlord_phone: str
    landlord_address: str
    tenant_name: str
    tenant_phone: Optional[str]
    tenant_email: Optional[str]
    property_address: str
    property_city: str
    property_zip: str
    rent_amount: float
    amount_owed: float
    notice_date: str
    notice_details: str
    reason: str
    lease_type: str
    military_check: bool = False
    signature_data: Optional[str] = None
    documents: List[str] = []
    submitted_at: str
    status: str = "submitted"  # submitted, processing, approved, rejected, filed
    assigned_by: Optional[str] = None
    assigned_at: Optional[str] = None
    official_case_number: Optional[str] = None
    filing_date: Optional[str] = None
    clerk_notes: Optional[str] = None
    rejection_reason: Optional[str] = None

class CaseUpdate(BaseModel):
    status: Optional[str] = None
    official_case_number: Optional[str] = None
    filing_date: Optional[str] = None
    clerk_notes: Optional[str] = None
    rejection_reason: Optional[str] = None

class DashboardStats(BaseModel):
    total_cases: int
    pending_review: int
    processing: int
    approved: int
    rejected: int
    court_filed: int
    recent_submissions: List[Dict[str, Any]]

# Helper functions
def load_cases() -> List[Dict[str, Any]]:
    """Load cases from JSON file"""
    if os.path.exists(CASES_DB_FILE):
        with open(CASES_DB_FILE, 'r') as f:
            return json.load(f)
    return []

def save_cases(cases: List[Dict[str, Any]]):
    """Save cases to JSON file"""
    with open(CASES_DB_FILE, 'w') as f:
        json.dump(cases, f, indent=2, default=str)

def get_case_files(case_id: str) -> List[str]:
    """Get list of files for a case"""
    case_dir = Path(CASES_DIR) / case_id
    if case_dir.exists():
        return [f.name for f in case_dir.iterdir() if f.is_file()]
    return []

def create_case_folder(case_id: str):
    """Create folder for case documents"""
    case_dir = Path(CASES_DIR) / case_id
    case_dir.mkdir(exist_ok=True)
    return case_dir

# Authentication middleware (simplified for demo)
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify authentication token"""
    # In production, validate JWT token
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"username": "admin"}

# API Endpoints
@app.get("/api/dashboard/stats")
async def get_dashboard_stats(user: dict = Depends(verify_token)):
    """Get dashboard statistics"""
    cases = load_cases()
    
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    
    recent_cases = [
        case for case in cases 
        if datetime.fromisoformat(case['submitted_at'].replace('Z', '+00:00')) >= week_ago
    ][:5]
    
    stats = {
        "total_cases": len(cases),
        "pending_review": len([c for c in cases if c['status'] == 'submitted']),
        "processing": len([c for c in cases if c['status'] == 'processing']),
        "approved": len([c for c in cases if c['status'] == 'approved']),
        "rejected": len([c for c in cases if c['status'] == 'rejected']),
        "court_filed": len([c for c in cases if c['status'] == 'filed']),
        "recent_submissions": recent_cases
    }
    
    return stats

@app.get("/api/dashboard/cases")
async def get_cases(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    user: dict = Depends(verify_token)
):
    """Get all cases with optional filtering"""
    cases = load_cases()
    
    # Apply filters
    if status and status != "all":
        cases = [c for c in cases if c['status'] == status]
    
    if search:
        search_lower = search.lower()
        cases = [
            c for c in cases
            if (search_lower in c['case_id'].lower() or
                search_lower in c['landlord_name'].lower() or
                search_lower in c['tenant_name'].lower() or
                search_lower in c['property_address'].lower())
        ]
    
    if start_date:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        cases = [c for c in cases if datetime.fromisoformat(c['submitted_at'].replace('Z', '+00:00')) >= start]
    
    if end_date:
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        cases = [c for c in cases if datetime.fromisoformat(c['submitted_at'].replace('Z', '+00:00')) <= end]
    
    # Sort by submission date (newest first)
    cases.sort(key=lambda x: x['submitted_at'], reverse=True)
    
    return {"cases": cases, "count": len(cases)}

@app.get("/api/dashboard/cases/{case_id}")
async def get_case_details(case_id: str, user: dict = Depends(verify_token)):
    """Get detailed information for a specific case"""
    cases = load_cases()
    case = next((c for c in cases if c['case_id'] == case_id), None)
    
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Get list of documents
    case['documents_list'] = get_case_files(case_id)
    
    return case

@app.post("/api/dashboard/cases/{case_id}/update")
async def update_case(
    case_id: str, 
    update: CaseUpdate,
    user: dict = Depends(verify_token)
):
    """Update case status or information"""
    cases = load_cases()
    case_index = next((i for i, c in enumerate(cases) if c['case_id'] == case_id), None)
    
    if case_index is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Update case
    if update.status:
        cases[case_index]['status'] = update.status
        cases[case_index]['assigned_by'] = user['username']
        cases[case_index]['assigned_at'] = datetime.now().isoformat()
    
    if update.official_case_number:
        cases[case_index]['official_case_number'] = update.official_case_number
    
    if update.filing_date:
        cases[case_index]['filing_date'] = update.filing_date
    
    if update.clerk_notes:
        cases[case_index]['clerk_notes'] = update.clerk_notes
    
    if update.rejection_reason:
        cases[case_index]['rejection_reason'] = update.rejection_reason
    
    save_cases(cases)
    
    return {"success": True, "case": cases[case_index]}

@app.get("/api/dashboard/cases/{case_id}/documents")
async def get_case_documents(case_id: str, user: dict = Depends(verify_token)):
    """Get list of documents for a case"""
    documents = get_case_files(case_id)
    return {"case_id": case_id, "documents": documents}

@app.get("/api/dashboard/cases/{case_id}/documents/{filename}")
async def download_document(
    case_id: str, 
    filename: str, 
    user: dict = Depends(verify_token)
):
    """Download a specific document"""
    file_path = Path(CASES_DIR) / case_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/pdf"
    )

@app.get("/api/dashboard/cases/{case_id}/download-all")
async def download_all_documents(case_id: str, user: dict = Depends(verify_token)):
    """Download all documents for a case as ZIP"""
    case_dir = Path(CASES_DIR) / case_id
    if not case_dir.exists():
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Create in-memory ZIP file
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in case_dir.iterdir():
            if file_path.is_file():
                zip_file.write(file_path, file_path.name)
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={case_id}_documents.zip"
        }
    )

@app.post("/api/dashboard/cases/{case_id}/reassign")
async def reassign_case_number(
    case_id: str,
    official_case_number: str,
    user: dict = Depends(verify_token)
):
    """Reassign official case number"""
    cases = load_cases()
    case_index = next((i for i, c in enumerate(cases) if c['case_id'] == case_id), None)
    
    if case_index is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    cases[case_index]['official_case_number'] = official_case_number
    cases[case_index]['status'] = 'filed'
    cases[case_index]['assigned_by'] = user['username']
    cases[case_index]['assigned_at'] = datetime.now().isoformat()
    cases[case_index]['filing_date'] = datetime.now().date().isoformat()
    
    save_cases(cases)
    
    return {"success": True, "new_case_number": official_case_number}

@app.get("/api/dashboard/export/csv")
async def export_cases_csv(user: dict = Depends(verify_token)):
    """Export all cases as CSV"""
    cases = load_cases()
    
    # Create CSV content
    csv_lines = ["Case ID,Landlord,Tenant,Property,Amount Owed,Status,Submitted,Official Case #,Filing Date"]
    
    for case in cases:
        csv_lines.append(
            f"{case['case_id']},"
            f"{case['landlord_name']},"
            f"{case['tenant_name']},"
            f"{case['property_address']},"
            f"{case['amount_owed']},"
            f"{case['status']},"
            f"{case['submitted_at']},"
            f"{case.get('official_case_number', '')},"
            f"{case.get('filing_date', '')}"
        )
    
    csv_content = "\n".join(csv_lines)
    
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=eviction_cases_{datetime.now().date()}.csv"
        }
    )

@app.get("/api/dashboard/reports/monthly")
async def get_monthly_report(user: dict = Depends(verify_token)):
    """Get monthly statistics report"""
    cases = load_cases()
    
    # Group by month
    monthly_stats = {}
    for case in cases:
        submitted_date = datetime.fromisoformat(case['submitted_at'].replace('Z', '+00:00'))
        month_key = submitted_date.strftime("%Y-%m")
        
        if month_key not in monthly_stats:
            monthly_stats[month_key] = {
                "total": 0,
                "filed": 0,
                "rejected": 0,
                "pending": 0,
                "total_amount": 0
            }
        
        monthly_stats[month_key]["total"] += 1
        monthly_stats[month_key]["total_amount"] += case['amount_owed']
        
        if case['status'] == 'filed':
            monthly_stats[month_key]["filed"] += 1
        elif case['status'] == 'rejected':
            monthly_stats[month_key]["rejected"] += 1
        elif case['status'] in ['submitted', 'processing', 'approved']:
            monthly_stats[month_key]["pending"] += 1
    
    # Convert to list sorted by month
    report = []
    for month, stats in sorted(monthly_stats.items(), reverse=True):
        report.append({
            "month": month,
            **stats
        })
    
    return {"monthly_report": report}

# Initialize sample data
@app.on_event("startup")
async def startup_event():
    """Initialize sample data if needed"""
    if not os.path.exists(CASES_DB_FILE):
        sample_cases = [
            {
                "case_id": "HOU-2024-1706092000-1234",
                "landlord_name": "John Smith Properties LLC",
                "landlord_email": "john@smithproperties.com",
                "landlord_phone": "(478) 555-0123",
                "landlord_address": "123 Business Ave, Warner Robins, GA 31088",
                "tenant_name": "Robert Johnson",
                "tenant_phone": "(478) 555-9876",
                "tenant_email": "rjohnson@email.com",
                "property_address": "123 Main St, Warner Robins, GA 31088",
                "property_city": "Warner Robins",
                "property_zip": "31088",
                "rent_amount": 1200.00,
                "amount_owed": 1850.00,
                "notice_date": "2024-01-15",
                "notice_details": "Posted on front door on 01/15/2024",
                "reason": "Non-Payment of Rent",
                "lease_type": "Month-to-Month",
                "military_check": False,
                "documents": ["demand_notice.pdf", "affidavit.pdf", "summons.pdf", "scra_form.pdf"],
                "submitted_at": "2024-01-24T14:30:00Z",
                "status": "submitted"
            },
            {
                "case_id": "HOU-2024-1706091800-5678",
                "landlord_name": "Mary Wilson",
                "landlord_email": "mwilson@email.com",
                "landlord_phone": "(478) 555-2345",
                "landlord_address": "456 Home St, Perry, GA 31069",
                "tenant_name": "David Miller",
                "tenant_phone": "(478) 555-8765",
                "tenant_email": "dmiller@email.com",
                "property_address": "456 Oak Ave, Perry, GA 31069",
                "property_city": "Perry",
                "property_zip": "31069",
                "rent_amount": 950.00,
                "amount_owed": 2450.00,
                "notice_date": "2024-01-10",
                "notice_details": "Certified mail #700512345678",
                "reason": "Lease Violation",
                "lease_type": "Fixed Term Lease",
                "military_check": True,
                "documents": ["demand_notice.pdf", "affidavit.pdf", "summons.pdf", "scra_form.pdf"],
                "submitted_at": "2024-01-23T11:20:00Z",
                "status": "processing",
                "assigned_by": "admin",
                "assigned_at": "2024-01-23T14:00:00Z"
            },
            {
                "case_id": "HOU-2024-1706091600-9012",
                "landlord_name": "Georgia Property Management",
                "landlord_email": "info@gapm.com",
                "landlord_phone": "(478) 555-3456",
                "landlord_address": "789 Corporate Blvd, Warner Robins, GA 31088",
                "tenant_name": "Sarah Williams",
                "tenant_phone": "(478) 555-7654",
                "tenant_email": "swilliams@email.com",
                "property_address": "789 Pine Rd, Centerville, GA 31028",
                "property_city": "Centerville",
                "property_zip": "31028",
                "rent_amount": 1400.00,
                "amount_owed": 3200.00,
                "notice_date": "2024-01-05",
                "notice_details": "Personal delivery on 01/05/2024",
                "reason": "Property Damage",
                "lease_type": "Fixed Term Lease",
                "military_check": False,
                "documents": ["demand_notice.pdf", "affidavit.pdf", "summons.pdf", "scra_form.pdf"],
                "submitted_at": "2024-01-22T09:45:00Z",
                "status": "approved",
                "assigned_by": "admin",
                "assigned_at": "2024-01-22T14:30:00Z"
            },
            {
                "case_id": "HOU-2024-1706091400-3456",
                "landlord_name": "Thomas Anderson",
                "landlord_email": "tanderson@email.com",
                "landlord_phone": "(478) 555-4567",
                "landlord_address": "321 Personal Dr, Warner Robins, GA 31088",
                "tenant_name": "Jennifer Brown",
                "tenant_phone": "(478) 555-6543",
                "tenant_email": "jbrown@email.com",
                "property_address": "321 Elm St, Warner Robins, GA 31088",
                "property_city": "Warner Robins",
                "property_zip": "31088",
                "rent_amount": 650.00,
                "amount_owed": 950.00,
                "notice_date": "2024-01-12",
                "notice_details": "Posted and mailed on 01/12/2024",
                "reason": "Holdover (Lease Expired)",
                "lease_type": "Month-to-Month",
                "military_check": False,
                "documents": ["demand_notice.pdf", "affidavit.pdf", "summons.pdf", "scra_form.pdf"],
                "submitted_at": "2024-01-21T16:10:00Z",
                "status": "filed",
                "official_case_number": "HOU-MC-2024-01234",
                "filing_date": "2024-01-22",
                "clerk_notes": "Documents complete, ready for filing",
                "assigned_by": "admin",
                "assigned_at": "2024-01-22T10:15:00Z"
            }
        ]
        
        save_cases(sample_cases)
        
        # Create sample document folders
        for case in sample_cases:
            case_dir = create_case_folder(case["case_id"])
            # Create sample PDF files
            for doc in case["documents"]:
                sample_pdf = case_dir / doc
                if not sample_pdf.exists():
                    # Create empty PDF file
                    sample_pdf.write_bytes(b'%PDF-1.4\n%Sample PDF for demonstration\n')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
