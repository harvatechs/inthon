const vscode = require('vscode');
const http = require('http');
const child_process = require('child_process');
const path = require('path');
const fs = require('fs');

let statusDiagnosticCollection;
let outputChannel;
let serverProcess = null;

function activate(context) {
    outputChannel = vscode.window.createOutputChannel("INTHON VM");
    context.subscriptions.push(outputChannel);

    statusDiagnosticCollection = vscode.languages.createDiagnosticCollection('inthon');
    context.subscriptions.push(statusDiagnosticCollection);

    // 1. Run Diagnostics (Syntax & Semantics checks)
    const runCheck = async (document) => {
        if (document.languageId !== 'inthon') return;

        const source = document.getText();
        try {
            const result = await makeRequest('/check', { source });
            const diagnostics = [];

            if (result && result.errors) {
                result.errors.forEach(err => {
                    // Normalize line/col (1-indexed to 0-indexed)
                    const line = Math.max(0, (err.line || 1) - 1);
                    const col = Math.max(0, (err.col || 1) - 1);
                    const range = new vscode.Range(line, col, line, col + 15);
                    diagnostics.push(new vscode.Diagnostic(
                        range,
                        err.message || 'INTHON semantic analyzer error',
                        vscode.DiagnosticSeverity.Error
                    ));
                });
            }

            statusDiagnosticCollection.set(document.uri, diagnostics);
        } catch (e) {
            console.error('INTHON IDE Server check failed:', e);
        }
    };

    // Diagnostics triggers
    vscode.workspace.onDidOpenTextDocument(runCheck, null, context.subscriptions);
    vscode.workspace.onDidSaveTextDocument(runCheck, null, context.subscriptions);
    vscode.workspace.onDidChangeTextDocument(event => runCheck(event.document), null, context.subscriptions);

    // Run check on active document at start
    if (vscode.window.activeTextEditor) {
        runCheck(vscode.window.activeTextEditor.document);
    }

    // 2. Document Formatting Provider
    const formattingProvider = vscode.languages.registerDocumentFormattingEditProvider('inthon', {
        async provideDocumentFormattingEdits(document) {
            const source = document.getText();
            try {
                const result = await makeRequest('/format', { source });
                if (result && result.ok && result.formatted) {
                    const firstLine = document.lineAt(0);
                    const lastLine = document.lineAt(document.lineCount - 1);
                    const fullRange = new vscode.Range(firstLine.range.start, lastLine.range.end);
                    return [vscode.TextEdit.replace(fullRange, result.formatted)];
                }
            } catch (e) {
                vscode.window.showWarningMessage('INTHON formatting server is not running.');
            }
            return [];
        }
    });
    context.subscriptions.push(formattingProvider);

    // 3. Command: Run current INTHON script
    const runScriptCommand = vscode.commands.registerCommand('inthon.run', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || editor.document.languageId !== 'inthon') {
            vscode.window.showErrorMessage('No active INTHON script open.');
            return;
        }

        const source = editor.document.getText();
        outputChannel.clear();
        outputChannel.show(true);
        outputChannel.appendLine(`[INTHON] Executing script ${editor.document.fileName}...`);

        try {
            const result = await makeRequest('/compile', { source, mock_tools: true });
            outputChannel.appendLine(`[INTHON] Execution output:\n`);
            if (result.ok) {
                outputChannel.appendLine(result.output || 'none');
                outputChannel.appendLine(`\n[INTHON] Cost: $${result.cost_usd || 0}`);
                outputChannel.appendLine(`[INTHON] Duration: ${result.duration_ms || 0}ms`);
            } else {
                outputChannel.appendLine(`[INTHON] Execution failed: ${result.error}`);
                if (result.traceback) {
                    outputChannel.appendLine(result.traceback);
                }
            }
        } catch (e) {
            outputChannel.appendLine(`[INTHON] Error contacting compiler server: ${e.message}`);
            vscode.window.showErrorMessage('Could not connect to the INTHON compiler server. Is it running on port 7474?');
        }
    });
    context.subscriptions.push(runScriptCommand);

    // 4. Auto-Fill Completion Provider
    const completionProvider = vscode.languages.registerCompletionItemProvider('inthon', {
        provideCompletionItems(document, position, token, context) {
            const completions = [];

            // Keywords
            const keywords = [
                { label: 'agent', detail: 'agent AgentName { ... }', insertText: 'agent ${1:MyAgent} {\n\tgoal "${2:objective}"\n\tplan {\n\t\t$0\n\t}\n}' },
                { label: 'goal', detail: 'goal "description"', insertText: 'goal "$0"' },
                { label: 'policy', detail: 'policy { ... }', insertText: 'policy {\n\tallow_network: true\n\tmax_tool_calls: 10\n}' },
                { label: 'plan', detail: 'plan { ... }', insertText: 'plan {\n\t$0\n}' },
                { label: 'inputs', detail: 'inputs { ... }', insertText: 'inputs {\n\t$0\n}' },
                { label: 'outputs', detail: 'outputs { ... }', insertText: 'outputs {\n\t$0\n}' },
                { label: 'fn', detail: 'fn func_name(arg: type) -> type { ... }', insertText: 'fn ${1:name}(${2:arg}: ${3:str}) -> ${4:str} {\n\t$0\n}' },
                { label: 'let', detail: 'let var = val', insertText: 'let ${1:variable} = $0' },
                { label: 'const', detail: 'const name = val', insertText: 'const ${1:NAME} = $0' },
                { label: 'use tool', detail: 'use tool skill.tool_name', insertText: 'use tool ${1:web.search}' },
                { label: 'use py', detail: 'use py.module as alias', insertText: 'use py.${1:module} as ${2:alias}' },
                { label: 'remember', detail: 'remember value in session', insertText: 'remember ${1:value} in ${2:session}' },
                { label: 'recall', detail: 'recall query from session', insertText: 'recall "${1:query}" from ${2:session}' },
                { label: 'approve', detail: 'approve action before run', insertText: 'approve ${1:action} before ${2:run}' }
            ];

            keywords.forEach(kw => {
                const item = new vscode.CompletionItem(kw.label, vscode.CompletionItemKind.Keyword);
                item.detail = kw.detail;
                if (kw.insertText) {
                    item.insertText = new vscode.SnippetString(kw.insertText);
                }
                completions.push(item);
            });

            // Types
            const types = ['str', 'int', 'float', 'bool', 'bytes', 'any', 'list', 'dict', 'tuple'];
            types.forEach(t => {
                const item = new vscode.CompletionItem(t, vscode.CompletionItemKind.TypeParameter);
                item.detail = `INTHON built-in type: ${t}`;
                completions.push(item);
            });

            // Policy properties
            const policies = [
                { label: 'allow_network', detail: 'allow_network: true|false', insertText: 'allow_network: ${1:true}' },
                { label: 'max_tool_calls', detail: 'max_tool_calls: integer', insertText: 'max_tool_calls: ${1:10}' },
                { label: 'max_cost_usd', detail: 'max_cost_usd: float', insertText: 'max_cost_usd: ${1:0.05}' },
                { label: 'allow_memory_persist', detail: 'allow_memory_persist: true|false', insertText: 'allow_memory_persist: ${1:true}' }
            ];
            policies.forEach(p => {
                const item = new vscode.CompletionItem(p.label, vscode.CompletionItemKind.Property);
                item.detail = p.detail;
                item.insertText = new vscode.SnippetString(p.insertText);
                completions.push(item);
            });

            // Built-in compiler tools
            const tools = [
                { label: 'web.search', detail: 'web.search(query, limit: int) -> list[dict]' },
                { label: 'web.read', detail: 'web.read(url) -> str' },
                { label: 'web.post', detail: 'web.post(url, data: dict) -> dict' }
            ];
            tools.forEach(tool => {
                const item = new vscode.CompletionItem(tool.label, vscode.CompletionItemKind.Function);
                item.detail = `Built-in Tool: ${tool.label}`;
                completions.push(item);
            });

            return completions;
        }
    });
    context.subscriptions.push(completionProvider);

    // 5. Automatically start the compiler server backend if not running
    ensureServerRunning();
}

function deactivate() {
    if (serverProcess) {
        outputChannel.appendLine('[INTHON] Stopping compiler server backend...');
        serverProcess.kill();
    }
}

// Helper function to query the local INTHON IDE server running on port 7474
function makeRequest(path, data, method = 'POST') {
    return new Promise((resolve, reject) => {
        const body = method === 'POST' ? JSON.stringify(data) : '';
        const options = {
            hostname: 'localhost',
            port: 7474,
            path: path,
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };

        if (method === 'POST') {
            options.headers['Content-Length'] = Buffer.byteLength(body);
        }

        const req = http.request(options, (res) => {
            let responseBody = '';
            res.setEncoding('utf-8');
            res.on('data', chunk => responseBody += chunk);
            res.on('end', () => {
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    try {
                        resolve(JSON.parse(responseBody));
                    } catch (e) {
                        resolve({ ok: true });
                    }
                } else {
                    reject(new Error(`Server returned status code ${res.statusCode}`));
                }
            });
        });

        req.on('error', err => reject(err));
        if (method === 'POST') {
            req.write(body);
        }
        req.end();
    });
}

// Automatically starts the INTHON IDE server from the workspace if not running
function ensureServerRunning() {
    makeRequest('/health', {}, 'GET')
        .then(() => {
            outputChannel.appendLine('[INTHON] Compiler server is already running on port 7474.');
        })
        .catch(err => {
            outputChannel.appendLine('[INTHON] Compiler server not detected. Attempting to start it automatically...');

            let scriptPath = '';
            let pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
            let wsRoot = '';

            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (workspaceFolders && workspaceFolders.length > 0) {
                wsRoot = workspaceFolders[0].uri.fsPath;
                scriptPath = path.join(wsRoot, 'ide', 'inthon_server.py');

                // Check for local virtual environment python
                const venvPythonWin = path.join(wsRoot, '.venv', 'Scripts', 'python.exe');
                const venvPythonNix = path.join(wsRoot, '.venv', 'bin', 'python');

                if (fs.existsSync(venvPythonWin)) {
                    pythonCmd = venvPythonWin;
                } else if (fs.existsSync(venvPythonNix)) {
                    pythonCmd = venvPythonNix;
                }
            } else if (vscode.window.activeTextEditor) {
                const activePath = vscode.window.activeTextEditor.document.fileName;
                const match = activePath.match(/(.*[\\/]ide)[\\/]/) || activePath.match(/(.*)[\\/]/);
                if (match) {
                    scriptPath = path.join(match[1], 'ide', 'inthon_server.py');
                }
            }

            if (scriptPath && fs.existsSync(scriptPath)) {
                outputChannel.appendLine(`[INTHON] Starting server script: ${scriptPath} using python binary: ${pythonCmd}`);
                
                serverProcess = child_process.spawn(pythonCmd, [scriptPath], {
                    cwd: wsRoot || undefined
                });

                // Pipe outputs to show logs inside output channel for debugging
                serverProcess.stdout.on('data', (data) => {
                    outputChannel.appendLine(`[INTHON Server STDOUT] ${data.toString().trim()}`);
                });

                serverProcess.stderr.on('data', (data) => {
                    outputChannel.appendLine(`[INTHON Server STDERR] ${data.toString().trim()}`);
                });

                serverProcess.on('error', (err) => {
                    outputChannel.appendLine(`[INTHON Server] Failed to spawn process: ${err.message}`);
                });

                serverProcess.on('close', (code) => {
                    outputChannel.appendLine(`[INTHON Server] Process exited with code ${code}`);
                    serverProcess = null;
                });

                vscode.window.showInformationMessage('INTHON compiler server started automatically.');
            } else {
                vscode.window.showErrorMessage('INTHON compiler server is not running and script was not found. Please run: python ide/inthon_server.py');
            }
        });
}

module.exports = {
    activate,
    deactivate
};
