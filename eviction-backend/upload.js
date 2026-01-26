/**
 * Simple GitHub Upload Script
 * Add this script tag to index.html BEFORE </body>:
 * <script src="upload.js"></script>
 */

const BACKEND_URL = 'http://localhost:3000';

// Wait for DOM and existing scripts to load
window.addEventListener('load', function() {
    console.log('Upload script loaded');
    
    // Replace the Save to GitHub button function
    const saveBtn = document.getElementById('saveToGitHubBtn');
    if (saveBtn) {
        // Remove old listeners
        const newBtn = saveBtn.cloneNode(true);
        saveBtn.parentNode.replaceChild(newBtn, saveBtn);
        
        // Add new listener
        newBtn.addEventListener('click', uploadToGitHub);
        console.log('✓ Upload button configured');
    }
});

async function uploadToGitHub() {
    console.log('Starting upload...');
    
    // Show loading (reuse existing function)
    if (typeof showLoading === 'function') {
        showLoading('Uploading to GitHub...');
    }
    
    try {
        // Get case data (from global variables set by main script)
        if (!window.caseId || !window.formData || !window.generatedDocuments) {
            throw new Error('Case data not ready. Please complete all steps first.');
        }
        
        // Prepare documents
        const documents = {};
        for (const [type, doc] of Object.entries(window.generatedDocuments)) {
            documents[type] = doc.output('datauristring');
        }
        
        console.log(`Uploading case ${window.caseId}...`);
        
        // Send to backend
        const response = await fetch(`${BACKEND_URL}/api/upload-case`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                caseId: window.caseId,
                formData: window.formData,
                documents: documents
            })
        });
        
        const result = await response.json();
        
        if (typeof hideLoading === 'function') {
            hideLoading();
        }
        
        if (!response.ok || !result.success) {
            throw new Error(result.message || 'Upload failed');
        }
        
        console.log('✓ Upload successful');
        
        // Show success
        alert(`✅ Case Uploaded to GitHub!\n\n` +
              `Case ID: ${result.caseId}\n` +
              `Files: ${result.uploads.filter(u => u.success).length} uploaded\n\n` +
              `View: ${result.url}`);
        
    } catch (error) {
        console.error('Upload error:', error);
        
        if (typeof hideLoading === 'function') {
            hideLoading();
        }
        
        let message = error.message;
        let help = '';
        
        if (message.includes('fetch')) {
            help = '\n\nMake sure backend is running:\n  node server.js';
        }
        
        alert(`❌ Upload Failed\n\n${message}${help}\n\nDocuments saved locally - use Download buttons.`);
    }
}

// Test connection function
window.testBackend = async function() {
    try {
        const response = await fetch(`${BACKEND_URL}/health`);
        const data = await response.json();
        alert(`✅ Backend Connected!\n\nStatus: ${data.status}\nGitHub: ${data.github}`);
    } catch (error) {
        alert(`❌ Backend Not Running\n\nStart it with: node server.js`);
    }
};

console.log('Upload script ready. Backend:', BACKEND_URL);
