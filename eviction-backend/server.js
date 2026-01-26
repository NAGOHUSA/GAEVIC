/**
 * Simple Backend Server for Houston County Eviction System
 * 
 * SETUP:
 * 1. Install Node.js from nodejs.org
 * 2. Create folder: mkdir eviction-backend
 * 3. Put this file in that folder as server.js
 * 4. Create .env file (see below)
 * 5. Run: npm install express cors dotenv axios
 * 6. Start: node server.js
 */

const express = require('express');
const cors = require('cors');
const axios = require('axios');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json({ limit: '50mb' }));

// GitHub Config
const GITHUB = {
    owner: 'NAGOHUSA',
    repo: 'GAEVIC',
    branch: 'main',
    token: process.env.GITHUB_TOKEN
};

// Validate token on startup
if (!GITHUB.token) {
    console.error('❌ ERROR: GITHUB_TOKEN not set!');
    console.error('Create .env file with: GITHUB_TOKEN=your_GAEVICCV2_token');
    process.exit(1);
}

console.log(`✓ GitHub: ${GITHUB.owner}/${GITHUB.repo}`);

// Health check
app.get('/health', (req, res) => {
    res.json({ 
        status: 'OK',
        github: `${GITHUB.owner}/${GITHUB.repo}`
    });
});

// Test connection
app.get('/api/test', async (req, res) => {
    try {
        const response = await axios.get(
            `https://api.github.com/repos/${GITHUB.owner}/${GITHUB.repo}`,
            { headers: { Authorization: `token ${GITHUB.token}` } }
        );
        res.json({ success: true, repo: response.data.full_name });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// Upload case
app.post('/api/upload-case', async (req, res) => {
    console.log('📤 Upload request received');
    
    try {
        const { caseId, formData, documents } = req.body;
        
        if (!caseId || !formData || !documents) {
            return res.status(400).json({
                success: false,
                message: 'Missing required data'
            });
        }
        
        console.log(`Case: ${caseId}`);
        
        // Upload PDFs
        const uploads = [];
        for (const [type, base64Data] of Object.entries(documents)) {
            const filename = getFilename(type);
            const base64 = base64Data.includes('base64,') 
                ? base64Data.split('base64,')[1] 
                : base64Data;
            
            try {
                await uploadFile(
                    `cases/${caseId}/${filename}`,
                    base64,
                    `Upload ${filename} for ${caseId}`
                );
                uploads.push({ file: filename, success: true });
                console.log(`✓ ${filename}`);
            } catch (err) {
                uploads.push({ file: filename, success: false, error: err.message });
                console.log(`✗ ${filename}: ${err.message}`);
            }
        }
        
        // Update case_data.json
        await updateCaseData(formData);
        console.log('✓ case_data.json updated');
        
        res.json({
            success: true,
            caseId,
            uploads,
            url: `https://github.com/${GITHUB.owner}/${GITHUB.repo}/tree/${GITHUB.branch}/cases/${caseId}`
        });
        
    } catch (error) {
        console.error('❌', error.message);
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// Upload file to GitHub
async function uploadFile(path, base64Content, message) {
    const url = `https://api.github.com/repos/${GITHUB.owner}/${GITHUB.repo}/contents/${path}`;
    
    await axios.put(url, {
        message,
        content: base64Content,
        branch: GITHUB.branch
    }, {
        headers: {
            Authorization: `token ${GITHUB.token}`,
            Accept: 'application/vnd.github.v3+json'
        }
    });
}

// Update case_data.json
async function updateCaseData(newCase) {
    const path = 'cases/case_data.json';
    const url = `https://api.github.com/repos/${GITHUB.owner}/${GITHUB.repo}/contents/${path}`;
    
    let cases = [];
    let sha = null;
    
    // Get existing file
    try {
        const response = await axios.get(url, {
            headers: { Authorization: `token ${GITHUB.token}` }
        });
        sha = response.data.sha;
        cases = JSON.parse(Buffer.from(response.data.content, 'base64').toString());
        console.log(`Found ${cases.length} existing cases`);
    } catch (err) {
        if (err.response?.status !== 404) throw err;
        console.log('Creating new case_data.json');
    }
    
    // Add new case
    cases.push(newCase);
    
    // Upload
    const content = Buffer.from(JSON.stringify(cases, null, 2)).toString('base64');
    const body = {
        message: `Add case ${newCase.caseId}`,
        content,
        branch: GITHUB.branch
    };
    if (sha) body.sha = sha;
    
    await axios.put(url, body, {
        headers: {
            Authorization: `token ${GITHUB.token}`,
            Accept: 'application/vnd.github.v3+json'
        }
    });
}

// Get filename
function getFilename(type) {
    const names = {
        demand_notice: '7-Day_Demand_Notice.pdf',
        affidavit: 'Dispossessory_Affidavit.pdf',
        summons: 'Summons.pdf',
        scra_form: 'SCRA_Verification.pdf'
    };
    return names[type] || `${type}.pdf`;
}

// Start server
app.listen(PORT, () => {
    console.log(`\n🚀 Server running on http://localhost:${PORT}`);
    console.log(`\nEndpoints:`);
    console.log(`  GET  /health`);
    console.log(`  GET  /api/test`);
    console.log(`  POST /api/upload-case`);
    console.log(`\n✓ Ready\n`);
});

/**
 * CREATE THIS FILE: .env
 * 
 * GITHUB_TOKEN=your_GAEVICCV2_token_here
 * PORT=3000
 */
