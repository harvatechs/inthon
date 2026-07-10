// -------------------------------------------------------------
// INTHON Web Emulator & Academic Project Interactions
// -------------------------------------------------------------

const PRESETS = {
  research: `use tool web.search

agent ResearchAgent {
    goal "Research and store findings in memory"
    policy {
        allow_network: true
        allow_memory_persist: true
    }
    plan {
        let query = "agent-level reasoning compiler"
        let results = web.search(query, limit: 1)
        remember results in session
        recalled = recall "compiler" from session
        return recalled
    }
}`,
  payment: `agent PaymentAgent {
    goal "Process payments with approval gates"
    policy {
        allow_payment: true
    }
    plan {
        approve subscription_fee before pay
    }
}`,
  sandbox: `use py.pandas as pd

agent AnalyticsAgent {
    goal "Filter CSV datasets securely"
    policy {
        allow_fs: false // Strict local disk isolation
        max_tool_calls: 5
    }
    plan {
        // Safe Python execution via PyBridge wrappers
        let df = pd.DataFrame({"metrics": [10.5, 23.2, 5.0]})
        return df.mean()
    }
}`
};

const SIMULATION_LOGS = {
  research: [
    { type: 'compiler', text: '[Lexer] Analyzing token streams in examples/agent_research.inth' },
    { type: 'compiler', text: '[Parser] Lark parser grammar successfully built AST representation.' },
    { type: 'compiler', text: '[Semantic] Validating names, variables, and type compatibility.' },
    { type: 'compiler', text: '[Policy] Capability allow_network: TRUE verified.' },
    { type: 'run', text: '[Runtime] Spawning ResearchAgent in isolated memory workspace...' },
    { type: 'run', text: '[Tool Call] Invoking web.search("agent-level reasoning compiler", limit=1)...' },
    { type: 'run', text: '[Tool Response] Completed. Found 1 relevant result from web.' },
    { type: 'run', text: '[Trace] Emitting execution state log event:' },
    { type: 'trace', text: JSON.stringify({
      event_id: "evt_082",
      run_id: "run_8f0e",
      type: "tool_call",
      span: { file: "agent_research.inth", line: 11, col: 24 },
      data: { query: "agent-level reasoning compiler", returned_items: 1 },
      cost_usd: 0.002
    }, null, 2)},
    { type: 'run', text: 'Output: "INTHON: An agent-level compiler layer for tool transactions."' }
  ],
  payment: [
    { type: 'compiler', text: '[Lexer] Scanning tokens in examples/approval_gate.inth' },
    { type: 'compiler', text: '[Parser] Parser recognized policy block and payment expression.' },
    { type: 'compiler', text: '[Semantic] Checking variables subscription_fee and pay.' },
    { type: 'compiler', text: '[Policy] Allow payment transaction verified.' },
    { type: 'run', text: '[Runtime] Spawning PaymentAgent...' },
    { type: 'run', text: '[Policy] Halting execution. Approval required for transaction subscription_fee.' },
    { type: 'run', text: '[System] Human gate prompted: Approve payment of subscription_fee? (Y/N)' },
    { type: 'run', text: '[System] Human approved transaction synchronously. Resuming execution...' },
    { type: 'run', text: '[Trace] Emitting transaction trace event:' },
    { type: 'trace', text: JSON.stringify({
      event_id: "evt_091",
      run_id: "run_7c1d",
      type: "approval_gate",
      span: { file: "approval_gate.inth", line: 7, col: 9 },
      data: { item: "subscription_fee", approved: true },
      cost_usd: 0.0
    }, null, 2)},
    { type: 'run', text: 'Output: Transaction Approved.' }
  ],
  sandbox: [
    { type: 'compiler', text: '[Lexer] Parsing module imports...' },
    { type: 'compiler', text: '[Semantic] Checking import policy for pd (pandas)...' },
    { type: 'compiler', text: '[Policy] Safe bridge verification: pandas module is in allowlist.' },
    { type: 'compiler', text: '[Policy] File system check: allow_fs is set to FALSE.' },
    { type: 'run', text: '[Runtime] Executing plan in restricted environment...' },
    { type: 'run', text: '[PyBridge] Initializing Pandas DataFrame adapter...' },
    { type: 'run', text: '[Trace] Trace logged execution event:' },
    { type: 'trace', text: JSON.stringify({
      event_id: "evt_112",
      run_id: "run_9a2b",
      type: "pybridge_call",
      span: { file: "analytics.inth", line: 11, col: 18 },
      data: { module: "pandas", method: "DataFrame.mean", result: 12.9 },
      cost_usd: 0.0
    }, null, 2)},
    { type: 'run', text: 'Output: 12.9' }
  ]
};

const PIPELINE_STEPS = {
  lexer: {
    title: "01. Lex & Parse Phase",
    desc: "The source code is scanned into character segments and matching lexical tokens. We use a context-free grammar written in Lark (`grammar.lark`) to generate a concrete syntax tree, discarding spaces and layout semantics.",
    file: "Modules: lexer/tokenizer.py, parser/grammar.lark"
  },
  ast: {
    title: "02. AST Generation Phase",
    desc: "Transforms the parsing tree structures into a clean, typed Abstract Syntax Tree (AST). AST Nodes represent declarative expressions (like Agent declarations, variable declarations, and tool pipelines) for downstream evaluation.",
    file: "Modules: ast/nodes.py, parser/transformer.py"
  },
  semantic: {
    title: "03. Semantic Analysis & Type Check",
    desc: "Performs scope resolution and static semantic validation. Ensures all references, variable definitions, tool registrations, and PyBridge libraries exist and pass strict validation before runtime computation starts.",
    file: "Modules: semantic/analyzer.py, semantic/type_checker.py"
  },
  policy: {
    title: "04. Capability & Policy Checks",
    desc: "Statically and dynamically checks capability permissions. It cross-checks the agent policy block configurations (allow_network, allow_fs, max_cost) against the target capability limits, refusing to run if policy constraints are violated.",
    file: "Modules: policy/engine.py, policy/approval.py"
  },
  runtime: {
    title: "05. Sandbox Runtime",
    desc: "Evaluates the execution stream in a strict tree-walking execution backend. Evaluates tool calls, handles state persistence in session namespaces, wraps Python interop calls securely via PyBridge, and records execution traces synchronously.",
    file: "Modules: runtime/sandbox.py, runtime/interpreter.py"
  }
};

document.addEventListener('DOMContentLoaded', () => {
  let activePreset = 'research';
  let isExecuting = false;

  // Initialize Code Editor Preset
  const codeDisplay = document.getElementById('code-display');
  const consoleOutput = document.getElementById('console-output');
  const runBtn = document.getElementById('run-code-btn');
  const consoleStatus = document.getElementById('console-status-indicator');

  let pyodideInstance = null;
  let isPyodideReady = false;

  async function initPyodide() {
    if (consoleStatus) {
      consoleStatus.textContent = 'Booting';
      consoleStatus.style.color = 'var(--text-muted)';
    }
    if (consoleOutput) {
      consoleOutput.innerHTML = `
        <div class="console-line system-line">&gt; Loading WebAssembly Python environment...</div>
      `;
    }
    
    try {
      // 1. Load Pyodide WASM with interactive stdin handler for approval gates
      pyodideInstance = await loadPyodide({
        stdin: () => {
          const res = window.prompt("[INTHON APPROVAL REQUIRED]\nEnter 'y' to approve, or 'n' to reject:");
          return (res || 'n') + '\n';
        }
      });
      
      if (consoleOutput) {
        consoleOutput.innerHTML += `
          <div class="console-line system-line">&gt; Installing lark compiler parser package...</div>
        `;
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
      }
      
      // 2. Load micropip and install dependencies
      await pyodideInstance.loadPackage("micropip");
      const micropip = pyodideInstance.pyimport("micropip");
      await micropip.install(["lark", "pydantic", "jsonschema", "typer", "rich", "structlog"]);
      
      if (consoleOutput) {
        consoleOutput.innerHTML += `
          <div class="console-line system-line">&gt; Fetching and unpacking inthon package...</div>
        `;
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
      }
      
      // 3. Fetch inthon.zip compiler files
      const response = await fetch('assets/inthon.zip');
      if (!response.ok) throw new Error("Failed to fetch assets/inthon.zip");
      const zipData = await response.arrayBuffer();
      
      // Write zip data to Pyodide MEMFS
      pyodideInstance.FS.writeFile("inthon.zip", new Uint8Array(zipData));
      
      // Extract inthon.zip
      pyodideInstance.runPython(`
import zipfile
with zipfile.ZipFile("inthon.zip", "r") as zip_ref:
    zip_ref.extractall(".")
      `);
      
      // Inject python runner helper
      pyodideInstance.runPython(`
import sys
import json
from inthon.parser.parser import parse
from inthon.runtime.context import ExecutionContext
from inthon.runtime.interpreter import Interpreter
from inthon.tools.builtin_tools import register_builtins
from inthon.semantic.scope import SemanticError
from inthon.runtime.errors import IntHonRuntimeError

class TraceCapturer:
    def __init__(self):
        self.logs = []
    def emit(self, event_type, data=None):
        self.logs.append({"type": event_type, "data": data})

def run_inthon(code_str):
    logs = []
    logs.append(("[Compiler]", "Analyzing token stream & parsing Lark grammar..."))
    try:
        prog = parse(code_str)
        logs.append(("[Parser]", "Concrete Syntax Tree parsed and AST built successfully."))
        
        ctx = ExecutionContext()
        register_builtins(ctx.tools, mock=True)
        
        tracer = TraceCapturer()
        ctx.tracer = tracer
        
        interp = Interpreter(ctx)
        logs.append(("[Runtime]", "Spawning isolated sandbox workspace..."))
        
        res = interp.run(prog)
        logs.append(("[Runtime]", f"Execution completed. Result: {res}"))
        
        for event in tracer.logs:
            logs.append(("[Trace]", f"Event '{event['type']}':\\n{json.dumps(event['data'], indent=2)}"))
            
        return json.dumps({"success": True, "logs": logs, "result": str(res)})
    except SemanticError as e:
        logs.append(("[Semantic Error]", f"Static check failed: {str(e)}"))
        return json.dumps({"success": False, "logs": logs, "error": str(e)})
    except IntHonRuntimeError as e:
        logs.append(("[Runtime Error]", f"Execution failed: {str(e)}"))
        return json.dumps({"success": False, "logs": logs, "error": str(e)})
    except Exception as e:
        logs.append(("[System Error]", f"General error: {str(e)}"))
        return json.dumps({"success": False, "logs": logs, "error": str(e)})
      `);
      
      isPyodideReady = true;
      if (consoleOutput) {
        consoleOutput.innerHTML += `
          <div class="console-line system-line">&gt; Live compiler environment initialized. Ready to execute code!</div>
        `;
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
      }
      if (consoleStatus) {
        consoleStatus.textContent = 'Ready';
        consoleStatus.style.color = '#28a745';
      }
    } catch (err) {
      console.error(err);
      if (consoleOutput) {
        consoleOutput.innerHTML += `
          <div class="console-line error-line">&gt; Initialization Error: ${err.message}</div>
        `;
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
      }
      if (consoleStatus) {
        consoleStatus.textContent = 'Error';
        consoleStatus.style.color = '#d73a49';
      }
    }
  }

  function loadPreset(presetName) {
    activePreset = presetName;
    if (codeDisplay) codeDisplay.textContent = PRESETS[presetName];
    
    // Clear tabs active state
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.classList.remove('active');
    });
    // Set active tab
    const activeTab = document.querySelector(`.tab-btn[data-preset="${presetName}"]`);
    if (activeTab) activeTab.classList.add('active');

    // Reset console
    if (consoleOutput) {
      if (isPyodideReady) {
        consoleOutput.innerHTML = `<div class="console-line system-line">&gt; Code loaded. Ready to execute ${presetName} agent.</div>`;
      } else {
        consoleOutput.innerHTML = `<div class="console-line system-line">&gt; Code loaded. Ready to execute ${presetName} agent (WASM still initializing).</div>`;
      }
    }
    if (consoleStatus && isPyodideReady) {
      consoleStatus.textContent = 'Ready';
      consoleStatus.style.color = '#28a745';
    }
  }

  // Bind Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      if (isExecuting) return;
      loadPreset(e.target.getAttribute('data-preset'));
    });
  });

  // Run Button Logic
  if (runBtn) {
    runBtn.addEventListener('click', async () => {
      if (isExecuting) return;
      
      if (!isPyodideReady) {
        if (consoleOutput) {
          consoleOutput.innerHTML += '<div class="console-line error-line">&gt; Live compiler environment is booting. Please wait...</div>';
          consoleOutput.scrollTop = consoleOutput.scrollHeight;
        }
        return;
      }

      isExecuting = true;
      runBtn.disabled = true;
      if (consoleStatus) {
        consoleStatus.textContent = 'Running';
        consoleStatus.style.color = 'var(--color-accent)';
      }

      if (consoleOutput) consoleOutput.innerHTML = '<div class="console-line system-line">&gt; Initiating INTHON environment runtime...</div>';

      const code = codeDisplay.innerText || codeDisplay.textContent;

      try {
        const runResultStr = pyodideInstance.globals.get('run_inthon')(code);
        const runResult = JSON.parse(runResultStr);
        
        const steps = runResult.logs;
        for (let i = 0; i < steps.length; i++) {
          await delay(Math.floor(Math.random() * 80) + 40); // fast execution simulation
          
          const stepText = steps[i];
          let type = 'run';
          if (stepText.startsWith('[Compiler]') || stepText.startsWith('[Parser]')) {
            type = 'compiler';
          } else if (stepText.startsWith('[Semantic Error]') || stepText.startsWith('[Runtime Error]') || stepText.startsWith('[System Error]')) {
            type = 'error';
          } else if (stepText.startsWith('[Trace]')) {
            type = 'trace';
          }
          
          let lineClass = 'compiler-line';
          if (type === 'run') lineClass = 'run-line';
          if (type === 'error') lineClass = 'error-line';
          
          let content = stepText;
          if (type === 'trace') {
            content = `<pre class="trace-json"><code>${stepText.substring(8)}</code></pre>`;
          }

          if (consoleOutput) {
            consoleOutput.innerHTML += `<div class="console-line ${lineClass}">${content}</div>`;
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
          }
        }

        if (runResult.success) {
          if (consoleStatus) {
            consoleStatus.textContent = 'Ready';
            consoleStatus.style.color = '#28a745';
          }
        } else {
          if (consoleStatus) {
            consoleStatus.textContent = 'Failed';
            consoleStatus.style.color = '#d73a49';
          }
        }
      } catch (runErr) {
        if (consoleOutput) {
          consoleOutput.innerHTML += `<div class="console-line error-line">[System Error] ${runErr.message}</div>`;
          consoleOutput.scrollTop = consoleOutput.scrollHeight;
        }
        if (consoleStatus) {
          consoleStatus.textContent = 'Error';
          consoleStatus.style.color = '#d73a49';
        }
      }
      
      isExecuting = false;
      runBtn.disabled = false;
    });
  }

  function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Load first default preset if codeDisplay exists
  if (codeDisplay) {
    loadPreset('research');
  }

  // Initialize Pyodide compiler environment
  initPyodide();

  // Pipeline Interactive Hover Logic
  const flowSteps = document.querySelectorAll('.flow-step');
  const detailPanel = document.getElementById('pipeline-details');
  const detailTitle = document.getElementById('detail-title');
  const detailDesc = document.getElementById('detail-desc');
  const detailBadge = document.getElementById('detail-badge');

  flowSteps.forEach(step => {
    step.addEventListener('mouseenter', () => {
      updateDetails(step.getAttribute('data-step'));
    });

    step.addEventListener('click', () => {
      flowSteps.forEach(s => s.classList.remove('active'));
      step.classList.add('active');
      updateDetails(step.getAttribute('data-step'));
    });
  });

  function updateDetails(stepKey) {
    const info = PIPELINE_STEPS[stepKey];
    if (info) {
      if (detailTitle) detailTitle.textContent = info.title;
      if (detailDesc) detailDesc.textContent = info.desc;
      if (detailBadge) {
        detailBadge.textContent = info.file;
        detailBadge.style.display = 'inline-block';
      }
    }
  }

  // Guide Sidebar Toggle Logic
  const sidebarItems = document.querySelectorAll('.sidebar-item');
  const guideSections = document.querySelectorAll('.guide-section');

  if (sidebarItems.length > 0) {
    sidebarItems.forEach(item => {
      item.addEventListener('click', () => {
        const targetId = item.getAttribute('data-target');

        // Update active class on sidebar items
        sidebarItems.forEach(i => i.classList.remove('active'));
        item.classList.add('active');

        // Update active class on sections
        guideSections.forEach(section => {
          if (section.id === targetId) {
            section.classList.add('active');
          } else {
            section.classList.remove('active');
          }
        });

        // Scroll to top of reading pane
        const mainPane = document.querySelector('.guide-content');
        if (mainPane) {
          mainPane.scrollTop = 0;
        }
      });
    });
  }

  // Citation Copy Button Logic
  const copyCitationBtn = document.getElementById('btn-copy-citation');
  const citationContent = document.getElementById('bibtex-citation');
  if (copyCitationBtn && citationContent) {
    copyCitationBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(citationContent.textContent.trim()).then(() => {
        const originalText = copyCitationBtn.textContent;
        copyCitationBtn.textContent = 'Copied!';
        copyCitationBtn.style.color = '#22863a';
        copyCitationBtn.style.borderColor = 'rgba(34, 134, 58, 0.3)';
        copyCitationBtn.style.backgroundColor = 'rgba(34, 134, 58, 0.04)';
        setTimeout(() => {
          copyCitationBtn.textContent = originalText;
          copyCitationBtn.style.color = '';
          copyCitationBtn.style.borderColor = '';
          copyCitationBtn.style.backgroundColor = '';
        }, 2000);
      });
    });
  }

  // Installation Copy Buttons Logic
  const copyInstallButtons = document.querySelectorAll('.btn-copy-install');
  copyInstallButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-target');
      const targetCode = document.getElementById(targetId);
      if (targetCode) {
        navigator.clipboard.writeText(targetCode.textContent.trim()).then(() => {
          btn.classList.add('copied');
          const originalSVG = btn.innerHTML;
          // Set to checkmark SVG
          btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
          setTimeout(() => {
            btn.classList.remove('copied');
            btn.innerHTML = originalSVG;
          }, 2000);
        });
      }
    });
  });

  // Toggle installation options
  const toggleButtons = document.querySelectorAll('.toggle-btn');
  const installPanes = document.querySelectorAll('.install-pane');
  toggleButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      // Deactivate all buttons
      toggleButtons.forEach(b => b.classList.remove('active'));
      // Activate clicked button
      btn.classList.add('active');

      const targetTab = btn.getAttribute('data-tab');
      installPanes.forEach(pane => {
        if (pane.id === `pane-${targetTab}`) {
          pane.style.display = 'block';
        } else {
          pane.style.display = 'none';
        }
      });
    });
  });
});

