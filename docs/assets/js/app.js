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
    logs.append("[Compiler] Analyzing token stream & parsing Lark grammar...")
    try:
        prog = parse(code_str)
        logs.append("[Parser] Concrete Syntax Tree parsed and AST built successfully.")
        
        ctx = ExecutionContext()
        register_builtins(ctx.tools, mock=True)
        
        tracer = TraceCapturer()
        ctx.tracer = tracer
        
        interp = Interpreter(ctx)
        logs.append("[Runtime] Spawning isolated sandbox workspace...")
        
        res = interp.run(prog)
        logs.append(f"[Runtime] Execution completed. Result: {res}")
        
        for event in tracer.logs:
            evt_type = event.get("type", "")
            evt_data = json.dumps(event.get("data"), indent=2)
            logs.append(f"[Trace] Event '{evt_type}':\n{evt_data}")

            
        return json.dumps({"success": True, "logs": logs, "result": str(res)})
    except SemanticError as e:
        logs.append(f"[Semantic Error] Static check failed: {str(e)}")
        return json.dumps({"success": False, "logs": logs, "error": str(e)})
    except IntHonRuntimeError as e:
        logs.append(f"[Runtime Error] Execution failed: {str(e)}")
        return json.dumps({"success": False, "logs": logs, "error": str(e)})
    except Exception as e:
        logs.append(f"[System Error] General error: {str(e)}")
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

  // Theme Toggle Management
  const themeToggleBtn = document.getElementById('theme-toggle-btn');
  
  // Apply initial theme from localStorage
  const currentTheme = localStorage.getItem('inthon-theme') || 'light';
  if (currentTheme === 'dark') {
    document.documentElement.classList.add('dark-theme');
  }

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', () => {
      const isDark = document.documentElement.classList.toggle('dark-theme');
      localStorage.setItem('inthon-theme', isDark ? 'dark' : 'light');
    });
  }

  // Guide Sidebar Toggle Logic
  const sidebarItems = document.querySelectorAll('.sidebar-item');
  const guideSections = document.querySelectorAll('.guide-section');
  const tocList = document.getElementById('toc-list');
  const mainPane = document.querySelector('.guide-content');

  function generateTOC() {
    if (!tocList || !mainPane) return;
    tocList.innerHTML = '';
    
    // Find active section
    const activeSection = document.querySelector('.guide-section.active');
    if (!activeSection) return;

    const headings = activeSection.querySelectorAll('h2, h3');
    if (headings.length === 0) {
      const emptyMsg = document.createElement('li');
      emptyMsg.className = 'toc-item';
      emptyMsg.textContent = 'On this page';
      emptyMsg.style.cursor = 'default';
      emptyMsg.style.color = 'var(--text-muted)';
      tocList.appendChild(emptyMsg);
      return;
    }

    headings.forEach((heading, index) => {
      // Ensure heading has an ID
      if (!heading.id) {
        heading.id = 'guide-heading-' + index;
      }
      
      const item = document.createElement('li');
      item.className = 'toc-item' + (heading.tagName === 'H3' ? ' depth-h3' : ' depth-h2');
      item.textContent = heading.textContent;
      item.setAttribute('data-target', heading.id);
      
      item.addEventListener('click', (e) => {
        e.preventDefault();
        heading.scrollIntoView({ behavior: 'smooth' });
        
        // Highlight active TOC item
        document.querySelectorAll('.toc-item').forEach(el => el.classList.remove('active'));
        item.classList.add('active');
      });
      
      tocList.appendChild(item);
    });
    
    setupTOCScrollObserver(headings);
  }

  function setupTOCScrollObserver(headings) {
    if (headings.length === 0) return;
    
    const observerOptions = {
      root: mainPane,
      rootMargin: '0px 0px -60% 0px',
      threshold: 0
    };
    
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const id = entry.target.id;
          document.querySelectorAll('.toc-item').forEach(item => {
            if (item.getAttribute('data-target') === id) {
              item.classList.add('active');
            } else {
              item.classList.remove('active');
            }
          });
        }
      });
    }, observerOptions);
    
    headings.forEach(heading => observer.observe(heading));
  }

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
        if (mainPane) {
          mainPane.scrollTop = 0;
        }
        
        // Re-generate Table of Contents
        generateTOC();
      });
    });
  }

  // Sidebar Search Filter Logic
  const searchInput = document.getElementById('sidebar-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase().trim();
      sidebarItems.forEach(item => {
        const text = item.textContent.toLowerCase();
        if (text.includes(query)) {
          item.style.display = 'block';
        } else {
          item.style.display = 'none';
        }
      });
    });
  }

  // Dynamically wrap pre code blocks with headers and copy buttons
  function wrapCodeBlocks() {
    const preBlocks = document.querySelectorAll('.guide-content pre, .spec-section pre');
    preBlocks.forEach((pre) => {
      if (pre.parentNode.classList.contains('code-wrapper')) return;
      
      const code = pre.querySelector('code');
      if (!code) return;
      
      let lang = 'code';
      const classes = code.className.split(' ');
      classes.forEach((c) => {
        if (c.startsWith('language-')) {
          lang = c.replace('language-', '');
        }
      });
      
      const wrapper = document.createElement('div');
      wrapper.className = 'code-wrapper';
      
      const header = document.createElement('div');
      header.className = 'code-header';
      header.innerHTML = `
        <span>${lang.toUpperCase()}</span>
        <button class="btn-copy-code" title="Copy code">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
        </button>
      `;
      
      pre.parentNode.insertBefore(wrapper, pre);
      wrapper.appendChild(header);
      wrapper.appendChild(pre);
      
      const copyBtn = header.querySelector('.btn-copy-code');
      copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(code.textContent.trim()).then(() => {
          copyBtn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
          copyBtn.style.color = '#28a745';
          setTimeout(() => {
            copyBtn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
            copyBtn.style.color = '';
          }, 2000);
        });
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
      toggleButtons.forEach(b => b.classList.remove('active'));
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

  // Initialize Code Blocks & TOC
  wrapCodeBlocks();
  generateTOC();
});

