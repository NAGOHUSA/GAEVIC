<?php
// Houston County Eviction System - Webhook Handler
// Receives case data and automatically creates/updates GitHub repository

// Enable error reporting for debugging
error_reporting(E_ALL);
ini_set('display_errors', 1);

// Set headers for JSON response
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization, X-Event-Type, X-Case-ID, X-Source');

// Handle preflight requests
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

// GitHub Configuration
define('GITHUB_OWNER', 'NAGOHUSA');
define('GITHUB_REPO', 'GAEVIC');
define('GITHUB_BRANCH', 'main');
define('GITHUB_TOKEN', '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'); // Replace with your actual GitHub token
define('GITHUB_API_URL', 'https://api.github.com');

// Webhook secret for verification (optional)
define('WEBHOOK_SECRET', 'houston-county-eviction-secret-2024');

// Log file for debugging
define('LOG_FILE', __DIR__ . '/webhook_logs.txt');

/**
 * Log messages to file and optionally to response
 */
function log_message($message, $data = null, $include_in_response = false) {
    $timestamp = date('Y-m-d H:i:s');
    $log_entry = "[$timestamp] $message";
    
    if ($data !== null) {
        $log_entry .= " | Data: " . json_encode($data, JSON_PRETTY_PRINT);
    }
    
    $log_entry .= PHP_EOL;
    
    // Write to log file
    file_put_contents(LOG_FILE, $log_entry, FILE_APPEND);
    
    if ($include_in_response) {
        return $log_entry;
    }
    
    return null;
}

/**
 * Send JSON response
 */
function send_response($success, $message, $data = null, $http_code = 200) {
    http_response_code($http_code);
    
    $response = [
        'success' => $success,
        'message' => $message,
        'timestamp' => date('c'),
        'data' => $data
    ];
    
    // Add log entry to response if in debug mode
    if (isset($_GET['debug']) || isset($_POST['debug'])) {
        $response['debug'] = [
            'received_data' => json_decode(file_get_contents('php://input'), true),
            'server_info' => [
                'method' => $_SERVER['REQUEST_METHOD'],
                'content_type' => $_SERVER['CONTENT_TYPE'] ?? 'Not set',
                'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? 'Not set'
            ]
        ];
    }
    
    echo json_encode($response, JSON_PRETTY_PRINT);
    exit();
}

/**
 * Verify webhook signature (optional security)
 */
function verify_webhook_signature() {
    if (!defined('WEBHOOK_SECRET') || WEBHOOK_SECRET === '') {
        return true; // No secret configured
    }
    
    $signature = $_SERVER['HTTP_X_HUB_SIGNATURE_256'] ?? '';
    $payload = file_get_contents('php://input');
    
    if (empty($signature)) {
        return false;
    }
    
    $expected_signature = 'sha256=' . hash_hmac('sha256', $payload, WEBHOOK_SECRET);
    
    return hash_equals($expected_signature, $signature);
}

/**
 * Make GitHub API request
 */
function github_api_request($endpoint, $method = 'GET', $data = null) {
    $url = GITHUB_API_URL . $endpoint;
    
    $headers = [
        'Accept: application/vnd.github.v3+json',
        'User-Agent: Houston-County-Eviction-System',
        'Authorization: token ' . GITHUB_TOKEN
    ];
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);
    curl_setopt($ch, CURLOPT_TIMEOUT, 30);
    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
    
    if ($data !== null && ($method === 'POST' || $method === 'PUT')) {
        $json_data = json_encode($data);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $json_data);
        $headers[] = 'Content-Type: application/json';
        $headers[] = 'Content-Length: ' . strlen($json_data);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    }
    
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    curl_close($ch);
    
    return [
        'success' => $http_code >= 200 && $http_code < 300,
        'status_code' => $http_code,
        'response' => $response,
        'error' => $error,
        'data' => json_decode($response, true)
    ];
}

/**
 * Check if repository exists
 */
function github_repository_exists() {
    $endpoint = "/repos/" . GITHUB_OWNER . "/" . GITHUB_REPO;
    $result = github_api_request($endpoint);
    
    if ($result['success']) {
        log_message("Repository exists: " . GITHUB_OWNER . "/" . GITHUB_REPO);
        return true;
    }
    
    log_message("Repository does not exist or cannot be accessed: " . GITHUB_OWNER . "/" . GITHUB_REPO);
    return false;
}

/**
 * Create repository if it doesn't exist
 */
function create_github_repository() {
    // Check if repository already exists
    if (github_repository_exists()) {
        return ['success' => true, 'message' => 'Repository already exists'];
    }
    
    // Create repository
    $data = [
        'name' => GITHUB_REPO,
        'description' => 'Houston County Eviction Cases - Automated Storage',
        'private' => true,
        'auto_init' => true,
        'gitignore_template' => 'Node',
        'license_template' => 'mit'
    ];
    
    $endpoint = "/user/repos";
    $result = github_api_request($endpoint, 'POST', $data);
    
    if ($result['success']) {
        log_message("Repository created successfully: " . GITHUB_OWNER . "/" . GITHUB_REPO);
        return ['success' => true, 'message' => 'Repository created'];
    }
    
    log_message("Failed to create repository", $result);
    return ['success' => false, 'message' => 'Failed to create repository', 'details' => $result];
}

/**
 * Create or update file in GitHub repository
 */
function github_create_or_update_file($path, $content, $message) {
    // Check if file exists to get SHA for update
    $endpoint = "/repos/" . GITHUB_OWNER . "/" . GITHUB_REPO . "/contents/" . $path;
    $existing_file = github_api_request($endpoint);
    
    $data = [
        'message' => $message,
        'content' => base64_encode($content),
        'branch' => GITHUB_BRANCH
    ];
    
    // If file exists, add SHA to update it
    if ($existing_file['success']) {
        $data['sha'] = $existing_file['data']['sha'];
        log_message("Updating existing file: " . $path);
    } else {
        log_message("Creating new file: " . $path);
    }
    
    $result = github_api_request($endpoint, 'PUT', $data);
    
    if ($result['success']) {
        log_message("File created/updated successfully: " . $path);
        return ['success' => true, 'message' => 'File saved'];
    }
    
    log_message("Failed to create/update file: " . $path, $result);
    return ['success' => false, 'message' => 'Failed to save file', 'details' => $result];
}

/**
 * Create case folder and files in GitHub
 */
function create_case_in_github($case_data) {
    log_message("Starting GitHub case creation", ['case_id' => $case_data['caseId']]);
    
    // Ensure repository exists
    $repo_result = create_github_repository();
    if (!$repo_result['success']) {
        return $repo_result;
    }
    
    $case_id = $case_data['caseId'];
    $case_folder = "cases/{$case_id}/";
    
    // Create folder structure (GitHub doesn't have folders, we create README to establish folder)
    $readme_content = "# Case: {$case_id}\n\n";
    $readme_content .= "**Houston County Eviction Case**\n\n";
    $readme_content .= "**Case ID:** {$case_id}\n";
    $readme_content .= "**Status:** {$case_data['status']}\n";
    $readme_content .= "**Filed:** " . date('F j, Y, g:i a', strtotime($case_data['filingDate'])) . "\n";
    $readme_content .= "**Landlord:** {$case_data['landlord']['name']}\n";
    $readme_content .= "**Tenant:** {$case_data['tenant']['name']}\n";
    $readme_content .= "**Property:** {$case_data['property']['address']}\n\n";
    $readme_content .= "---\n\n";
    $readme_content .= "*This case was automatically filed via the Houston County Eviction System*\n";
    
    // Save README.md
    $readme_result = github_create_or_update_file(
        $case_folder . "README.md",
        $readme_content,
        "Add README for case {$case_id}"
    );
    
    if (!$readme_result['success']) {
        return $readme_result;
    }
    
    // Save case data as JSON
    $json_content = json_encode($case_data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
    $json_result = github_create_or_update_file(
        $case_folder . "case_data.json",
        $json_content,
        "Add case data for {$case_id}"
    );
    
    if (!$json_result['success']) {
        return $json_result;
    }
    
    // Create document placeholder files (actual PDFs would be generated separately)
    $documents = [
        '7-Day_Demand_Notice.md' => "# 7-Day Demand Notice\n\n**Case:** {$case_id}\n**Generated:** " . date('c') . "\n\n*This document would be generated as a PDF in a production system.*",
        'Dispossessory_Affidavit.md' => "# Dispossessory Affidavit\n\n**Case:** {$case_id}\n**Generated:** " . date('c') . "\n\n*This document would be generated as a PDF in a production system.*",
        'Summons.md' => "# Summons\n\n**Case:** {$case_id}\n**Generated:** " . date('c') . "\n\n*This document would be generated as a PDF in a production system.*",
        'SCRA_Verification.md' => "# SCRA Verification\n\n**Case:** {$case_id}\n**Generated:** " . date('c') . "\n\n*This document would be generated as a PDF in a production system.*"
    ];
    
    foreach ($documents as $filename => $content) {
        $doc_result = github_create_or_update_file(
            $case_folder . $filename,
            $content,
            "Add {$filename} for case {$case_id}"
        );
        
        if (!$doc_result['success']) {
            log_message("Warning: Failed to create document {$filename}", $doc_result);
        }
    }
    
    // Create webhook response file
    $webhook_response = [
        'webhook_received' => date('c'),
        'case_id' => $case_id,
        'status' => 'processed',
        'github_repo' => GITHUB_OWNER . '/' . GITHUB_REPO,
        'github_path' => $case_folder,
        'files_created' => array_keys($documents),
        'note' => 'Case successfully stored in GitHub repository'
    ];
    
    $webhook_result = github_create_or_update_file(
        $case_folder . "webhook_response.json",
        json_encode($webhook_response, JSON_PRETTY_PRINT),
        "Add webhook response for case {$case_id}"
    );
    
    log_message("Case creation completed", ['case_id' => $case_id, 'folder' => $case_folder]);
    
    return [
        'success' => true,
        'message' => 'Case created successfully in GitHub',
        'case_id' => $case_id,
        'github_repo' => GITHUB_OWNER . '/' . GITHUB_REPO,
        'github_path' => $case_folder,
        'view_url' => 'https://github.com/' . GITHUB_OWNER . '/' . GITHUB_REPO . '/tree/main/' . $case_folder
    ];
}

/**
 * Process incoming webhook data
 */
function process_webhook($data) {
    log_message("Processing webhook request", ['event' => $data['event'] ?? 'unknown']);
    
    // Validate required data
    if (!isset($data['caseId']) || empty($data['caseId'])) {
        return ['success' => false, 'message' => 'Missing caseId'];
    }
    
    if (!isset($data['data']) || empty($data['data'])) {
        return ['success' => false, 'message' => 'Missing case data'];
    }
    
    $case_id = $data['caseId'];
    $case_data = $data['data'];
    
    log_message("Processing case", ['case_id' => $case_id]);
    
    // Store in GitHub
    $github_result = create_case_in_github($case_data);
    
    if ($github_result['success']) {
        // Optional: Send notification email or other processing
        send_notification($case_id, $case_data);
        
        return [
            'success' => true,
            'message' => 'Case processed successfully',
            'case_id' => $case_id,
            'github' => $github_result,
            'timestamp' => date('c')
        ];
    }
    
    return $github_result;
}

/**
 * Send notification (placeholder for email/SMS/other notifications)
 */
function send_notification($case_id, $case_data) {
    // This is a placeholder for notification functionality
    // In production, you could:
    // 1. Send email to court clerk
    // 2. Send SMS to landlord
    // 3. Update dashboard database
    // 4. Trigger other workflows
    
    log_message("Notification placeholder for case", ['case_id' => $case_id]);
    
    // Example: Log notification (replace with actual notification code)
    $notification_log = __DIR__ . '/notifications.log';
    $log_entry = date('Y-m-d H:i:s') . " | Case: {$case_id} | Landlord: {$case_data['landlord']['name']} | Status: {$case_data['status']}\n";
    file_put_contents($notification_log, $log_entry, FILE_APPEND);
    
    return true;
}

/**
 * Main webhook handler
 */
function main() {
    log_message("=== Webhook Request Started ===");
    
    // Verify request method
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        send_response(false, 'Method not allowed. Use POST.', null, 405);
    }
    
    // Get raw input
    $raw_input = file_get_contents('php://input');
    
    if (empty($raw_input)) {
        send_response(false, 'No data received', null, 400);
    }
    
    // Parse JSON data
    $data = json_decode($raw_input, true);
    
    if (json_last_error() !== JSON_ERROR_NONE) {
        send_response(false, 'Invalid JSON data: ' . json_last_error_msg(), null, 400);
    }
    
    // Verify webhook signature (optional)
    if (!verify_webhook_signature()) {
        log_message("Webhook signature verification failed");
        send_response(false, 'Invalid webhook signature', null, 401);
    }
    
    // Log received data
    log_message("Webhook data received", $data);
    
    // Process the webhook
    $result = process_webhook($data);
    
    // Send response
    if ($result['success']) {
        send_response(true, $result['message'], $result, 200);
    } else {
        send_response(false, $result['message'], $result, 500);
    }
}

// Create logs directory if it doesn't exist
if (!file_exists(__DIR__ . '/logs')) {
    mkdir(__DIR__ . '/logs', 0755, true);
}

// Handle the request
try {
    main();
} catch (Exception $e) {
    log_message("Unhandled exception: " . $e->getMessage(), ['trace' => $e->getTraceAsString()]);
    send_response(false, 'Internal server error: ' . $e->getMessage(), null, 500);
}
