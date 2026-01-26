<?php
// test_simple.php - Diagnostic tool
error_reporting(E_ALL);
ini_set('display_errors', 1);

echo "<h1>Webhook Diagnostic Tool</h1>";
echo "<p>Server Time: " . date('Y-m-d H:i:s') . "</p>";
echo "<p>PHP Version: " . PHP_VERSION . "</p>";
echo "<p>Request Method: " . $_SERVER['REQUEST_METHOD'] . "</p>";
echo "<p>Request URI: " . $_SERVER['REQUEST_URI'] . "</p>";

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    echo "<h2 style='color: green;'>✓ POST request received!</h2>";
    $input = file_get_contents('php://input');
    echo "<p>Raw input: " . htmlspecialchars($input) . "</p>";
} else {
    echo "<h2>Test POST request:</h2>";
    echo "<button onclick='testPost()'>Test POST to this same URL</button>";
    echo "<div id='result'></div>";
    
    echo "<script>
    async function testPost() {
        const result = document.getElementById('result');
        result.innerHTML = 'Testing...';
        
        try {
            const response = await fetch('test_simple.php', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({test: 'data', time: new Date().toISOString()})
            });
            const text = await response.text();
            result.innerHTML = '<h3>Response:</h3><pre>' + text + '</pre>';
        } catch (error) {
            result.innerHTML = '<p style=\"color: red;\">Error: ' + error.message + '</p>';
        }
    }
    </script>";
}
?>
