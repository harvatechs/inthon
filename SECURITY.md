# Security Policy

INTHON takes security and sandbox safety very seriously. As a language layer designed to execute AI-generated code, ensuring capability restrictions, import limitations, and execution quotas are strictly enforced is our top priority.

---

## Supported Versions

Only the latest release version of INTHON receives security updates. If a security vulnerability is identified, we will backport patches to the current stable branch as soon as possible.

| Version | Supported |
| :--- | :--- |
| **v0.1.x** | :white_check_mark: Supported (Current) |
| **< v0.1.0** | :x: Unsupported |

---

## Reporting a Vulnerability

If you discover a security issue, particularly:
* Sandbox escapes (executing unapproved Python modules or shell commands)
* Bypassing memory/CPU resource constraints
* Bypassing approval gates or budget policies
* Replay/audit log spoofing

**Please do not report it through public GitHub issues.** Instead, report it privately to our security team:

* **Email**: Send detailed vulnerability reports to **security@harvatechs.com** (or **contact@harvatechs.com**).
* **Details to Include**: 
  * A clear description of the vulnerability.
  * An INTHON code example (.inth script) demonstrating the bypass or exploit.
  * System/Python environment details under which the issue was reproduced.
  * Your suggested remediation, if any.

We will acknowledge receipt of your report within **48 hours** and provide a tracking status update.

---

## Disclosure Process

We follow a coordinated vulnerability disclosure process:
1. Once a report is validated, our team works on a mitigation patch.
2. A security release will be published containing the fix.
3. We will credit you for finding and reporting the issue (if you wish to be credited) in our release notes.
4. We ask that you give us **90 days** from the initial report to patch and release before disclosing the issue publicly.
