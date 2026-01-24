import React, { useState, useEffect } from 'react';
import DocumentSigner from '../components/DocumentSigner';

const SignDocuments = () => {
  const [caseId, setCaseId] = useState('');
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Get case ID from URL
    const urlParams = new URLSearchParams(window.location.search);
    const caseParam = urlParams.get('case');
    
    if (caseParam) {
      setCaseId(caseParam);
      loadDocuments(caseParam);
    } else {
      setError('No case ID provided');
      setLoading(false);
    }
  }, []);

  const loadDocuments = async (id) => {
    try {
      const response = await fetch(`/api/documents/${id}/list`);
      if (!response.ok) throw new Error('Failed to load documents');
      
      const data = await response.json();
      setDocuments(data.documents);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDocumentsSigned = (result) => {
    // Redirect to payment page
    window.location.href = `/payment?case=${caseId}`;
  };

  const handleBack = () => {
    window.location.href = `/case/${caseId}`;
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner"></div>
        <p>Loading documents...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-container">
        <h2>Error Loading Documents</h2>
        <p>{error}</p>
        <button onClick={() => window.location.href = '/'}>
          Return to Home
        </button>
      </div>
    );
  }

  return (
    <div className="sign-documents-page">
      <DocumentSigner
        caseId={caseId}
        documents={documents}
        onDocumentsSigned={handleDocumentsSigned}
        onBack={handleBack}
      />
    </div>
  );
};

export default SignDocuments;
