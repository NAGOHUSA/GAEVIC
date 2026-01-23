import React, { useState } from 'react';
import './NewCase.css';

const HoustonCountyEvictionForm = () => {
  const [formData, setFormData] = useState({
    // Landlord Information
    landlord_name: '',
    landlord_address: '',
    landlord_phone: '',
    landlord_email: '',
    
    // Property Information
    property_address: '',
    property_city: 'Warner Robins', // Default for Houston County
    property_zip: '',
    county: 'Houston',
    
    // Tenant Information
    tenant_name: '',
    tenant_address_same: true,
    tenant_phone: '',
    tenant_email: '',
    
    // Case Details
    lease_type: 'month-to-month',
    rent_amount: '',
    late_fees: '',
    reason: 'non-payment', // non-payment, lease-violation, holdover
    amount_owed: '',
    last_payment_date: '',
    notice_served_date: '',
    notice_type: 'Demand for Possession',
    
    // Court Information
    court_type: 'Magistrate Court',
    case_type: 'Dispossessory',
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    // Submit to backend API
    const response = await fetch('/api/cases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    });
    
    if (response.ok) {
      const result = await response.json();
      window.location.href = `/case/${result.case_id}/documents`;
    }
  };

  return (
    <div className="eviction-form">
      <h1>Houston County, Georgia - Eviction Filing</h1>
      <form onSubmit={handleSubmit}>
        {/* Form sections here */}
        <div className="form-section">
          <h2>Landlord Information</h2>
          <input 
            type="text" 
            placeholder="Full Legal Name"
            value={formData.landlord_name}
            onChange={(e) => setFormData({...formData, landlord_name: e.target.value})}
            required
          />
          {/* More fields... */}
        </div>
        
        <button type="submit" className="submit-btn">
          Generate Documents & Continue
        </button>
      </form>
    </div>
  );
};

export default HoustonCountyEvictionForm;
