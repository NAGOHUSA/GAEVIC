import os
import json
import base64
from datetime import datetime
import requests
from pathlib import Path

class GitHubCaseSubmitter:
    def __init__(self, github_token, repo_owner, repo_name):
        self.github_token = github_token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        self.headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def submit_case(self, case_data):
        """Submit a complete eviction case to GitHub repository"""
        try:
            case_id = case_data.get("case_id")
            if not case_id:
                case_id = f"HOU-{datetime.now().year}-{int(datetime.now().timestamp())}"
                case_data["case_id"] = case_id
            
            # Create case directory
            case_dir = f"cases/{case_id}"
            
            # 1. Save case data as JSON
            case_json = json.dumps(case_data.get("case_data", {}), indent=2)
            self.create_file(
                path=f"{case_dir}/case_data.json",
                content=case_json,
                message=f"Add case data for {case_id}"
            )
            
            # 2. Save each document
            documents = case_data.get("documents", {})
            for doc_type, doc_base64 in documents.items():
                filename = self.get_doc_filename(doc_type)
                # Decode base64 PDF
                pdf_content = base64.b64decode(doc_base64)
                # Encode for GitHub API
                encoded_content = base64.b64encode(pdf_content).decode('utf-8')
                
                self.create_file(
                    path=f"{case_dir}/{filename}",
                    content=encoded_content,
                    message=f"Add {doc_type} for case {case_id}",
                    is_binary=True
                )
            
            # 3. Update index file
            self.update_case_index(case_id, case_data)
            
            return {
                "success": True,
                "case_id": case_id,
                "github_path": f"{case_dir}/",
                "files_created": len(documents) + 1
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "case_id": case_id if 'case_id' in locals() else None
            }
    
    def create_file(self, path, content, message, is_binary=False):
        """Create or update a file in GitHub repository"""
        url = f"{self.base_url}/contents/{path}"
        
        # Check if file exists
        response = requests.get(url, headers=self.headers)
        
        data = {
            "message": message,
            "content": content if not is_binary else content
        }
        
        if response.status_code == 200:
            # File exists, get SHA for update
            existing_file = response.json()
            data["sha"] = existing_file["sha"]
        
        response = requests.put(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def update_case_index(self, case_id, case_data):
        """Update the index of all cases"""
        index_path = "cases/index.json"
        
        # Get current index
        url = f"{self.base_url}/contents/{index_path}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            existing_index = response.json()
            content = base64.b64decode(existing_index["content"]).decode('utf-8')
            index_data = json.loads(content)
            sha = existing_index["sha"]
        else:
            index_data = {"cases": []}
            sha = None
        
        # Add new case to index
        new_case = {
            "case_id": case_id,
            "landlord": case_data.get("case_data", {}).get("landlord", {}).get("name"),
            "tenant": case_data.get("case_data", {}).get("tenant", {}).get("name"),
            "property": case_data.get("case_data", {}).get("property", {}).get("address"),
            "submitted": datetime.now().isoformat(),
            "status": "submitted"
        }
        
        index_data["cases"].append(new_case)
        
        # Save updated index
        content = json.dumps(index_data, indent=2)
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        data = {
            "message": f"Update index with case {case_id}",
            "content": encoded_content
        }
        
        if sha:
            data["sha"] = sha
        
        response = requests.put(url, headers=self.headers, json=data)
        response.raise_for_status()
    
    def get_doc_filename(self, doc_type):
        """Get filename for document type"""
        filenames = {
            "demand_notice": "7-Day_Demand_Notice.pdf",
            "affidavit": "Dispossessory_Affidavit.pdf",
            "summons": "Summons.pdf",
            "scra_form": "SCRA_Verification.pdf"
        }
        return filenames.get(doc_type, f"{doc_type}.pdf")


# FastAPI endpoint to handle submissions
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

app = FastAPI()

class CaseSubmission(BaseModel):
    case_id: str
    case_data: Dict[str, Any]
    documents: Dict[str, str]  # base64 encoded PDFs
    timestamp: str

@app.post("/api/submit-to-github")
async def submit_case_to_github(submission: CaseSubmission):
    """API endpoint to submit case to GitHub"""
    try:
        # Load GitHub credentials from environment
        github_token = os.getenv("GITHUB_TOKEN")
        repo_owner = os.getenv("GITHUB_REPO_OWNER", "NAGOHUSA")
        repo_name = os.getenv("GITHUB_REPO_NAME", "GAEVIC")
        
        if not github_token:
            raise HTTPException(status_code=500, detail="GitHub token not configured")
        
        submitter = GitHubCaseSubmitter(github_token, repo_owner, repo_name)
        result = submitter.submit_case(submission.dict())
        
        if result["success"]:
            return {
                "success": True,
                "message": "Case submitted successfully",
                "case_id": result["case_id"],
                "github_url": f"https://github.com/{repo_owner}/{repo_name}/tree/main/{result['github_path']}",
                "files_created": result["files_created"]
            }
        else:
            raise HTTPException(status_code=500, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Submission failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
