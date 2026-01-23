#!/usr/bin/env python3
"""
Generate eviction documents for Houston County, Georgia
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import pdfkit

class HoustonCountyDocumentGenerator:
    def __init__(self, case_id, case_data):
        self.case_id = case_id
        self.case_data = case_data
        self.templates_dir = Path("templates")
        self.output_dir = Path(f"documents/{case_id}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.env = Environment(loader=FileSystemLoader(self.templates_dir))
        
        # Houston County specific information
        self.court_info = {
            "name": "Houston County Magistrate Court",
            "address": "202 Carl Vinson Parkway, Warner Robins, GA 31088",
            "phone": "(478) 542-2100",
            "chief_magistrate": "Hon. James W. Smith",
            "filing_fee": "$81.00"  # Current Houston County fee
        }
    
    def generate_eviction_notice(self):
        """Generate 7-Day Demand for Possession (GA specific)"""
        template = self.env.get_template("eviction_notice.html")
        
        html_content = template.render(
            case=self.case_data,
            court=self.court_info,
            generated_date=datetime.now().strftime("%B %d, %Y"),
            # Georgia-specific requirements
            georgia_code="OCGA § 44-7-50",
            notice_period="7 days" if self.case_data.get('lease_type') == 'month-to-month' else "30 days"
        )
        
        pdf_path = self.output_dir / "eviction_notice.pdf"
        pdfkit.from_string(html_content, str(pdf_path))
        
        return pdf_path
    
    def generate_affidavit(self):
        """Generate Sworn Affidavit for Houston County"""
        template = self.env.get_template("affidavit.html")
        
        html_content = template.render(
            case=self.case_data,
            court=self.court_info,
            today=datetime.now().strftime("%B %d, %Y"),
            notary_info={
                "name": "Available at filing",
                "commission_expires": "Indefinite"
            }
        )
        
        pdf_path = self.output_dir / "affidavit.pdf"
        pdfkit.from_string(html_content, str(pdf_path))
        
        return pdf_path
    
    def generate_dispossessory_warrant(self):
        """Generate Dispossessory Warrant (Georgia's term for eviction warrant)"""
        template = self.env.get_template("dispossessory_warrant.html")
        
        html_content = template.render(
            case=self.case_data,
            court=self.court_info,
            case_number=f"HOU-MC-{datetime.now().year}-{self.case_id}",
            constable_info={
                "name": "Houston County Sheriff's Office",
                "address": "202 Carl Vinson Parkway, Warner Robins, GA 31088"
            }
        )
        
        pdf_path = self.output_dir / "dispossessory_warrant.pdf"
        pdfkit.from_string(html_content, str(pdf_path))
        
        return pdf_path

def main():
    parser = argparse.ArgumentParser(description="Generate eviction documents")
    parser.add_argument("--case-id", required=True, help="Case ID")
    parser.add_argument("--data-file", help="JSON file with case data")
    
    args = parser.parse_args()
    
    # Load case data
    if args.data_file:
        with open(args.data_file, 'r') as f:
            case_data = json.load(f)
    else:
        # For GitHub Actions workflow
        import os
        case_data = json.loads(os.environ.get('CASE_DATA', '{}'))
    
    generator = HoustonCountyDocumentGenerator(args.case_id, case_data)
    
    # Generate all documents
    documents = {
        "eviction_notice": generator.generate_eviction_notice(),
        "affidavit": generator.generate_affidavit(),
        "dispossessory_warrant": generator.generate_dispossessory_warrant()
    }
    
    print(f"Documents generated: {list(documents.keys())}")

if __name__ == "__main__":
    main()
