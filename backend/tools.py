# tools.py
# Code Review Tools — analyze_code (SAST pattern scanner) + run_deep_scan (Semgrep)
# False positive reduction: placeholder detection, context-aware validation,
# function-scope try detection, test file awareness, security-context random check,
# Semgrep LOW confidence filtering


import re
import subprocess
import tempfile
import json
import os
import shutil
from typing import Dict


# ─────────────────────────────────────────────
# False positive helpers
# ─────────────────────────────────────────────

PLACEHOLDER_PATTERNS = [
    r'your[_\-]?\w+[_\-]?here',
    r'xxx+',
    r'\bplaceholder\b',
    r'\bchangeme\b',
    r'\bexample\b',
    r'\bdummy\b',
    r'\btest\b',
    r'\bsample\b',
    r'<.*?>',
    r'\$\{.*?\}',
    r'os\.getenv',
    r'environ',
]

UTILITY_PREFIXES = (
    "format_", "parse_", "convert_", "get_", "build_",
    "render_", "make_", "create_", "to_", "from_",
)

def _is_placeholder(value: str) -> bool:
    return any(re.search(p, value, re.IGNORECASE) for p in PLACEHOLDER_PATTERNS)


# ─────────────────────────────────────────────
# TOOL 1: Regex-based pattern scanner
# Fast, zero-dependency, runs instantly
# Covers OWASP Top 10 (2025) + CWE Top 25 patterns
# ─────────────────────────────────────────────


def analyze_code(code_content: str, language: str = "python") -> Dict:
    """
    Performs deep pattern analysis on submitted code.
    Detects hardcoded secrets, injection vulnerabilities, broken access control,
    cryptographic failures, security misconfiguration, missing error handling,
    performance issues, and style violations.
    Returns all findings organized by severity.
    """

    # ── Language gate — Python only ──
    PYTHON_ONLY = {"python", "py"}
    if language.lower() not in PYTHON_ONLY:
        return {
            "note": (
                f"Pattern scanner is optimized for Python only. "
                f"'{language}' code has been routed to run_deep_scan (Semgrep) "
                f"which has native {language} rulesets."
            ),
            "summary": {
                "total_issues": 0,
                "critical": 0, "high": 0, "medium": 0, "low": 0
            }
        }

    findings = {
        "hardcoded_secrets":         [],
        "injection_vulnerabilities": [],
        "broken_access_control":     [],
        "cryptographic_failures":    [],
        "security_misconfiguration": [],
        "missing_validation":        [],
        "missing_error_handling":    [],
        "performance_issues":        [],
        "style_violations":          [],
        "xxe_vulnerabilities":       [],
        "file_upload_issues":        [],
        "redos_vulnerabilities":     [],
        "summary":                   {},
    }

    lines = code_content.split("\n")

    # ── detect test/dev files upfront ──
    is_test_file = any(kw in code_content[:500] for kw in [
        "import pytest", "import unittest", "from django.test",
        "TestCase", "def test_", "conftest",
    ])
    is_dev_config = bool(re.search(
        r'(dev|local|test)\s*=\s*True|ENV\s*=\s*["\']dev',
        code_content, re.IGNORECASE
    ))

    # ── OWASP A07 / CWE-798: Hardcoded Credentials ──
    secret_patterns = {
        r'password\s*[=:]=?\s*["\'][^"\']+["\']':       "Hardcoded password",
        r'api_key\s*[=:]\s*["\'][^"\']+["\']':          "Hardcoded API key",
        r'secret\s*[=:]\s*["\'][^"\']+["\']':           "Hardcoded secret",
        r'token\s*[=:]\s*["\'][^"\']+["\']':            "Hardcoded token",
        r'aws_access_key\s*[=:]\s*["\'][^"\']+["\']':   "Hardcoded AWS key",
        r'database_url\s*[=:]\s*["\'][^"\']+["\']':     "Hardcoded database URL",
        r'private_key\s*[=:]\s*["\'][^"\']+["\']':      "Hardcoded private key",
        r'AKIA[0-9A-Z]{16}':                             "AWS Access Key ID exposed",
        r'mongodb(\+srv)?://\S+:\S+@':                   "Hardcoded MongoDB connection string",
        r'postgres(ql)?://\S+:\S+@':                     "Hardcoded PostgreSQL connection string",
        r'redis://:\S+@':                                "Hardcoded Redis connection string",
        r'sk-[a-zA-Z0-9]{32,}':                         "OpenAI API key exposed",
        r'gh[pousr]_[A-Za-z0-9_]{36,}':                 "GitHub token exposed",
        r'password\s*=\s*["\']["\']':                   "Empty/blank password in code",
        r'["\']PASSWORD["\']:\s*["\']["\']':            "Empty password in database config (CWE-521)",
        r'(postgresql|mysql|sqlite|mssql)://[^:@\s]+:@': "Empty password in database connection URL (CWE-521)",
        r'SQLALCHEMY_DATABASE_URI.*://[^:@\s]+:@':      "Empty password in SQLAlchemy URI (CWE-521)",
        r'if\s+password\s*==\s*["\'][^"\']+["\']':     "Hardcoded password comparison (CWE-798)",
        r'if\s+.*\s+==\s*["\'](?:admin|password|secret|root|letmein|12345)["\']': "Hardcoded credential comparison (CWE-798)",
    }

    for i, line in enumerate(lines, 1):
        for pattern, issue_type in secret_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                if _is_placeholder(line):
                    continue
                findings["hardcoded_secrets"].append({
                    "line":           i,
                    "content":        line.strip()[:80],
                    "issue":          issue_type,
                    "severity":       "CRITICAL",
                    "owasp":          "A07:2025 - Identification and Authentication Failures",
                    "cwe":            "CWE-798: Use of Hard-coded Credentials",
                    "recommendation": "Move to environment variable or secrets manager",
                })

    # ── OWASP A05 / CWE-89, 95, 78, 79, 502: Injection ──
    injection_patterns = {
        r'cursor\.execute\s*\(\s*f["\']':              ("SQL Injection via f-string",     "CRITICAL", "CWE-89",  "Use parameterized queries: cursor.execute(query, (param,))"),
        r'cursor\.execute\s*\([^,)]*\s*%\s*[^,)]*\)': ("SQL Injection via % format",     "CRITICAL", "CWE-89",  "Use parameterized queries: cursor.execute(query, (param,))"),
        r'\.format\s*\(.*\)\s*.*execute':              ("SQL Injection via .format()",    "CRITICAL", "CWE-89",  "Use parameterized queries"),
        r'eval\s*\(':                                  ("Arbitrary code execution",       "CRITICAL", "CWE-95",  "Never use eval(). Use ast.literal_eval() for safe data parsing"),
        r'exec\s*\(':                                  ("Arbitrary code execution",       "CRITICAL", "CWE-95",  "Avoid exec(). Redesign to eliminate dynamic code execution"),
        r'pickle\.loads?\s*\(':                        ("Unsafe deserialization",         "CRITICAL", "CWE-502", "Use JSON instead of pickle for untrusted data"),
        r'subprocess\.[a-z]+\(.*shell\s*=\s*True':    ("Shell injection risk",           "HIGH",     "CWE-78",  "Remove shell=True. Pass args as a list: subprocess.run(['cmd', arg])"),
        r'os\.system\s*\(':                            ("OS command injection",           "HIGH",     "CWE-78",  "Use subprocess.run() with argument list, not os.system()"),
        r'render_template_string\s*\(':                ("Server-Side Template Injection", "HIGH",     "CWE-94",  "Use render_template() with separate template files"),
        r'innerHTML\s*=':                              ("XSS via innerHTML",              "HIGH",     "CWE-79",  "Use textContent or sanitize with DOMPurify before DOM insertion"),
        r'cPickle\.loads?\s*\(':                       ("Unsafe cPickle deserialization", "CRITICAL", "CWE-502", "Use JSON instead of pickle/cPickle for untrusted data"),
        r'yaml\.load\s*\((?!.*SafeLoader)(?!.*safe_load)': ("yaml.load without SafeLoader", "HIGH", "CWE-502", "Use yaml.safe_load() or yaml.load(data, Loader=yaml.SafeLoader)"),
        r'\.xpath\s*\(.*%\s*':                         ("XPath injection via % format",   "HIGH",     "CWE-643", "Use parameterized XPath expressions; never concatenate user input into XPath"),
        r'\.xpath\s*\(.*\+':                           ("XPath injection via concatenation", "HIGH",  "CWE-643", "Use parameterized XPath expressions; never concatenate user input into XPath"),
        r'(?:etree|ET|xml|lxml)\..*\.findall\s*\(\s*(?:f["\']|[a-zA-Z_].*\+|[a-zA-Z_].*%|[a-zA-Z_].*\.format)': ("XPath injection via findall with user-controlled path", "HIGH", "CWE-643", "Verify XPath path is not user-controlled; use parameterized expressions"),
        r'FilterExpression\s*=\s*[^"\'\\n]*\+':       ("DynamoDB/NoSQL injection via string concatenation", "CRITICAL", "CWE-943", "Use parameterized expressions with ExpressionAttributeValues only"),
    }

    for i, line in enumerate(lines, 1):
        for pattern, (issue, severity, cwe, rec) in injection_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                findings["injection_vulnerabilities"].append({
                    "line":           i,
                    "content":        line.strip()[:80],
                    "issue":          issue,
                    "severity":       severity,
                    "owasp":          "A05:2025 - Injection",
                    "cwe":            cwe,
                    "recommendation": rec,
                })

    # ── OWASP A01 / CWE-284, 285, 295, 601: Broken Access Control ──
    access_patterns = {
        r'verify\s*=\s*False':                            ("SSL verification disabled",         "HIGH",     "CWE-295", "Never disable SSL verification in production"),
        r'CORS\s*\(.*origins\s*=\s*[\[\(]?\s*["\'\*]':   ("CORS allows all origins",           "HIGH",     "CWE-346", "Restrict CORS to specific trusted domains"),
        r'DEBUG\s*=\s*True':                              ("Debug mode enabled",                "HIGH",     "CWE-94",  "Set DEBUG=False in production — exposes stack traces and secrets"),
        r'allow_redirects\s*=\s*True':                    ("Open redirect risk",                "MEDIUM",   "CWE-601", "Validate redirect URLs against an explicit allowlist"),
        r'@app\.route.*methods.*["\']GET["\'].*password': ("Password over GET request",         "CRITICAL", "CWE-598", "Never send credentials via GET — use POST with body encryption"),
        r'send_file\s*\(.*%\s*':                          ("Resource injection via send_file (% format)", "HIGH", "CWE-641", "Validate and normalize file paths; use os.path.basename()"),
        r'send_file\s*\(.*\+\s*':                         ("Resource injection via send_file (concatenation)", "HIGH", "CWE-641", "Validate and normalize file paths; use os.path.basename()"),
        r'return\s+send_file\s*\(\s*(?!["\'])[a-zA-Z_][a-zA-Z0-9_]*\b': ("send_file with variable path — verify path is sanitized", "MEDIUM", "CWE-22", "Ensure paths from user input are sanitized with os.path.basename()"),
        r'bind\s*\(\s*\(\s*["\']0\.0\.0\.0["\']':        ("Server binding to all interfaces (0.0.0.0)", "MEDIUM", "CWE-605", "Bind to a specific IP unless intentional exposure is required"),
        r'ssl\.CERT_NONE':                                ("SSL certificate verification disabled (CERT_NONE)", "HIGH", "CWE-295", "Use ssl.CERT_REQUIRED with a proper CA certificate bundle"),
    }

    for i, line in enumerate(lines, 1):
        for pattern, (issue, severity, cwe, rec) in access_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                if "DEBUG" in line and (is_test_file or is_dev_config):
                    continue
                findings["broken_access_control"].append({
                    "line":           i,
                    "content":        line.strip()[:80],
                    "issue":          issue,
                    "severity":       severity,
                    "owasp":          "A01:2025 - Broken Access Control",
                    "cwe":            cwe,
                    "recommendation": rec,
                })

    # ── OWASP A04 / CWE-327, 326, 338: Cryptographic Failures ──
    crypto_patterns = {
        r'\bmd5\b':                                     ("Weak hash: MD5",                    "HIGH",     "CWE-327", "Use SHA-256 minimum; bcrypt/argon2 for passwords"),
        r'\bsha1\b':                                    ("Weak hash: SHA-1",                  "HIGH",     "CWE-327", "Use SHA-256 or stronger"),
        r'DES\s*\(':                                    ("Weak cipher: DES",                  "CRITICAL", "CWE-326", "Use AES-256-GCM instead"),
        r'RC4\s*\(':                                    ("Weak cipher: RC4",                  "CRITICAL", "CWE-326", "Use AES-256-GCM instead"),
        r'random\s*\.\s*(random|randint|choice)\s*\(': ("Insecure randomness",               "HIGH",     "CWE-338", "Use the secrets module for cryptographic randomness"),
        r'\bECB\b':                                     ("Weak cipher mode: ECB",             "CRITICAL", "CWE-327", "Use AES-GCM or AES-CBC with a random IV"),
        r'hashlib\.(md5|sha1)\s*\(':                   ("Weak hash function",                "HIGH",     "CWE-327", "Use hashlib.sha256() or passlib/bcrypt"),
        r'RSA\.generate\s*\(\s*(?:1024|512)\b':        ("Weak RSA key size (< 2048 bits)",   "HIGH",     "CWE-326", "Use RSA.generate(2048) or RSA.generate(4096) for strong security"),
        r'DSA\.generate\s*\(\s*(?:1024|512)\b':        ("Weak DSA key size (< 2048 bits)",   "HIGH",     "CWE-326", "Use DSA.generate(2048) or switch to ECDSA/Ed25519"),
        r'ssl\.wrap_socket\s*\(':                      ("Deprecated ssl.wrap_socket()",      "HIGH",     "CWE-327", "Use ssl.SSLContext with explicit TLS version and wrap_socket()"),
        r'jwt\.decode\s*\(.*verify\s*=\s*False':       ("JWT decoded without signature verification", "CRITICAL", "CWE-347", "Remove verify=False; always verify JWT signatures with the correct key"),
        r'verify_signature\s*.*False|options.*verify_signature.*False': ("JWT signature verification disabled", "CRITICAL", "CWE-347", "Never disable verify_signature; validate JWT with the correct signing key"),
        r'process_jwt\s*\(':                           ("JWT processed without verification", "CRITICAL", "CWE-347", "Call jwt.process_jwt() then validate with jwt.verify_jwt() using your signing key"),
        r'static_vector\s*=\s*b["\']':                ("Static IV used in block cipher",     "HIGH",     "CWE-329", "Generate a random IV with os.urandom(16) for each encryption operation"),
        r'AES\.MODE_CBC.*b["\'][x0\\]{1,4}["\']':     ("Possible static/hardcoded IV in AES-CBC", "HIGH", "CWE-329", "Use a randomly generated IV per encryption operation"),
        r'random\.seed\s*\(':                          ("random.seed() makes RNG predictable", "HIGH",   "CWE-339", "Do not seed random for cryptographic use; use secrets module instead"),
        r'random\.getrandbits\s*\(':                   ("random.getrandbits() is not cryptographically secure", "HIGH", "CWE-338", "Use secrets.randbits() or os.urandom() for cryptographic keys"),
        r'time\.clock\s*\(':                           ("Deprecated time.clock() — removed in Python 3.8", "LOW", "CWE-477", "Use time.perf_counter() or time.process_time()"),
        r'pbkdf2_hmac\s*\(.*b["\'][A-Za-z0-9+/=]{8,}["\']': ("Hardcoded salt in PBKDF2",   "HIGH",     "CWE-760", "Generate a unique random salt per password with os.urandom(16)"),
        r'mktemp\s*\(':                                ("Insecure temp file creation (mktemp is racey)", "HIGH", "CWE-377", "Use tempfile.mkstemp() or tempfile.NamedTemporaryFile()"),
    }

    for i, line in enumerate(lines, 1):
        for pattern, (issue, severity, cwe, rec) in crypto_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                if "random" in pattern and "seed" not in pattern and "getrandbits" not in pattern:
                    context = "\n".join(lines[max(0, i - 3):i + 3])
                    security_context = any(kw in context.lower() for kw in [
                        "token", "password", "secret", "key", "auth",
                        "session", "salt", "otp", "nonce",
                    ])
                    if not security_context:
                        continue
                findings["cryptographic_failures"].append({
                    "line":           i,
                    "content":        line.strip()[:80],
                    "issue":          issue,
                    "severity":       severity,
                    "owasp":          "A04:2025 - Cryptographic Failures",
                    "cwe":            cwe,
                    "recommendation": rec,
                })

    # ── OWASP A02 / CWE-16, 532, 390, 396: Security Misconfiguration ──
    misconfig_patterns = {
        r'import\s+\*':                          ("Wildcard import",            "LOW",      "CWE-1188", "Import only what you need"),
        r'except\s*:':                           ("Bare except clause",         "MEDIUM",   "CWE-390",  "Catch specific exceptions — bare except silently hides bugs"),
        r'except\s+Exception\s*:':              ("Overly broad exception",     "MEDIUM",   "CWE-396",  "Catch specific exception types where possible"),
        r'print\s*\(.*password':                 ("Credential in print output", "CRITICAL", "CWE-532",  "Never print credentials — use structured logging with masking"),
        r'print\s*\(.*token':                    ("Token in print output",      "HIGH",     "CWE-532",  "Never print secrets — use structured logging"),
        r'logging\.(info|debug|warning|error|critical)\s*\(.*(?:password|passwd|pwd)': ("Credential in log output", "CRITICAL", "CWE-532", "Never log credentials — mask sensitive fields"),
        r'logging\.(info|debug|warning|error|critical)\s*\(.*(?:token|secret|api_key|apikey)': ("Secret in log output", "HIGH", "CWE-532", "Never log secrets — mask sensitive fields"),
        r'logging\.(info|debug|warning|error|critical)\s*\(.*\+.*(?:name|input|user|data|query|request|param)': ("Log injection — user-controlled data in log output", "HIGH", "CWE-117", "Sanitize log inputs: strip newlines/CRLF before logging user-controlled values"),
        r'app\.logger\.(info|debug|warning|error)\s*\(.*\+': ("Log injection via Flask logger concatenation", "HIGH", "CWE-117", "Sanitize user-provided values before logging; avoid string concatenation"),
        r'traceback\.format_exc\s*\(\s*\)': ("Stack trace returned to client (information exposure)", "MEDIUM", "CWE-209", "Log stack traces server-side; return a generic error message to the client"),
        r'app\.run\s*\(.*debug\s*=\s*True': ("Flask debug mode enabled in app.run()", "HIGH", "CWE-215", "Set debug=False in production; debug mode exposes the interactive debugger"),
        r'os\.chmod\s*\(.*0o[67][0-7][0-7]': ("Insecure file permissions (world-readable/writable)", "MEDIUM", "CWE-732", "Use restrictive permissions: 0o600 for sensitive files, 0o700 for directories"),
    }

    for i, line in enumerate(lines, 1):
        for pattern, (issue, severity, cwe, rec) in misconfig_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                findings["security_misconfiguration"].append({
                    "line":           i,
                    "content":        line.strip()[:80],
                    "issue":          issue,
                    "severity":       severity,
                    "owasp":          "A02:2025 - Security Misconfiguration",
                    "cwe":            cwe,
                    "recommendation": rec,
                })

    # ── XXE Vulnerabilities (CWE-611, CWE-776, CWE-827) ──
    xxe_patterns = {
        r'lxml\.etree\.fromstring\s*\(':                       ("XXE risk — lxml.etree.fromstring without safe parser",     "HIGH",     "CWE-611", "Use etree.fromstring(data, parser=etree.XMLParser(resolve_entities=False))"),
        r'etree\.XMLParser\s*\(\s*resolve_entities\s*=\s*True': ("XXE via resolve_entities=True in XMLParser",              "CRITICAL", "CWE-611", "Set resolve_entities=False in etree.XMLParser()"),
        r'etree\.XMLParser\s*\(\s*\)':                         ("XXE risk — default lxml XMLParser; entity resolution may be on", "MEDIUM", "CWE-827", "Explicitly pass resolve_entities=False to etree.XMLParser()"),
        r'xml\.sax\.make_parser\s*\(':                         ("XXE risk — xml.sax parser may process external entities",  "HIGH",     "CWE-611", "Disable external entities: parser.setFeature(handler.feature_external_ges, False)"),
        r'feature_external_ges.*True|setFeature.*True':        ("XXE — external general entities explicitly enabled",        "CRITICAL", "CWE-611", "Set feature_external_ges to False to block external entity expansion"),
        r'ET\.fromstring\s*\(':                                ("XML bomb / XXE risk — ET.fromstring processes untrusted XML", "MEDIUM", "CWE-776", "Use defusedxml.ElementTree.fromstring() to prevent XML bomb and XXE attacks"),
    }

    for i, line in enumerate(lines, 1):
        for pattern, (issue, severity, cwe, rec) in xxe_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                findings["xxe_vulnerabilities"].append({
                    "line":           i,
                    "content":        line.strip()[:80],
                    "issue":          issue,
                    "severity":       severity,
                    "owasp":          "A05:2025 - Injection / A06:2025 - Vulnerable Components",
                    "cwe":            cwe,
                    "recommendation": rec,
                })

    # ── Open Redirect Patterns (CWE-601) ──
    open_redirect_patterns = {
        r'return\s+redirect\s*\(\s*request\.(args|form|GET|POST|values)': ("Open redirect via user-controlled URL (Flask redirect)", "HIGH", "CWE-601", "Validate redirect URLs against an explicit allowlist before redirecting"),
        r'return\s+redirect\s*\(\s*(?:url|target|next|dest|location|redirect_to)\b': ("Open redirect — unvalidated redirect target variable", "HIGH", "CWE-601", "Validate redirect URLs against an explicit domain allowlist"),
        r'HttpResponseRedirect\s*\(\s*request\.(GET|POST)': ("Open redirect via user-controlled URL (Django HttpResponseRedirect)", "HIGH", "CWE-601", "Validate redirect URLs against an explicit allowlist"),
        r'response(?:\.headers)?\s*\[.Location.\]\s*=\s*(?:url|target|next|redirect_to|request\.)': ("Open redirect via Location header manipulation", "HIGH", "CWE-601", "Validate and allowlist the URL before setting the Location header"),
    }

    for i, line in enumerate(lines, 1):
        for pattern, (issue, severity, cwe, rec) in open_redirect_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                findings["broken_access_control"].append({
                    "line":           i,
                    "content":        line.strip()[:80],
                    "issue":          issue,
                    "severity":       severity,
                    "owasp":          "A01:2025 - Broken Access Control",
                    "cwe":            cwe,
                    "recommendation": rec,
                })

    # ── File Upload Vulnerabilities (CWE-434) ──
    file_upload_patterns = {
        r'\.save\s*\(.*\.filename\b':                                        ("Unrestricted file upload — unsanitized filename", "HIGH", "CWE-434", "Use werkzeug.utils.secure_filename(); validate file extension against an allowlist"),
        r'open\s*\(.*(?:filename|img_name|file_name|uploaded_name).*["\']w': ("File write with potentially user-controlled filename", "HIGH", "CWE-434", "Sanitize filenames with secure_filename(); validate extensions before writing"),
        r'request\.files.*\.filename\b':                                      ("Direct use of user-supplied filename from upload",  "MEDIUM", "CWE-434", "Always sanitize uploaded filenames with werkzeug.utils.secure_filename()"),
    }

    for i, line in enumerate(lines, 1):
        for pattern, (issue, severity, cwe, rec) in file_upload_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                findings["file_upload_issues"].append({
                    "line":           i,
                    "content":        line.strip()[:80],
                    "issue":          issue,
                    "severity":       severity,
                    "owasp":          "A04:2025 - Insecure Design",
                    "cwe":            cwe,
                    "recommendation": rec,
                })

    # ── ReDoS / User-Controlled Regex Patterns (CWE-400, CWE-730) ──
    redos_patterns = {
        r're\.(search|match|fullmatch|findall|compile)\s*\(\s*request\.(args|form|GET|POST|values)\s*(?:\[|\.get)': ("ReDoS — user-controlled regex pattern passed to re functions", "HIGH", "CWE-730", "Never use untrusted input as a regex pattern; validate against a safe allowlist"),
        r'pattern\s*=\s*request\.(args|form|GET|POST|values)':                                                       ("User-controlled regex pattern stored in variable (ReDoS risk)", "HIGH", "CWE-400", "Validate and restrict regex patterns; do not allow untrusted input as regex"),
        r're\.compile\s*\(\s*pattern\s*\)':                                                                          ("Compiled regex from variable — verify pattern is not user-controlled", "MEDIUM", "CWE-730", "Ensure regex pattern variable does not derive from user input"),
    }

    for i, line in enumerate(lines, 1):
        for pattern, (issue, severity, cwe, rec) in redos_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                findings["redos_vulnerabilities"].append({
                    "line":           i,
                    "content":        line.strip()[:80],
                    "issue":          issue,
                    "severity":       severity,
                    "owasp":          "A05:2025 - Injection",
                    "cwe":            cwe,
                    "recommendation": rec,
                })

    # ── Path Traversal / Zip Slip Patterns (CWE-22) ──
    path_traversal_patterns = {
        r'\.extractall\s*\(':                                   ("Zip slip risk — archive.extractall() without member path validation", "HIGH",   "CWE-22",  "Validate member paths: reject entries containing '..' or starting with '/'"),
        r'os\.remove\s*\(\s*(?!["\'])\s*(?:request|args|form|GET|POST|params|input|user|query)': ("File deletion with user-controlled path — potential path traversal", "HIGH", "CWE-22", "Validate and sanitize path; use os.path.abspath and check against allowed directory"),
        r'open\s*\(\s*(?!["\'])[a-zA-Z_].*(?:request|args|form|GET|POST)': ("File open with user-controlled path", "HIGH", "CWE-22", "Never pass user input directly to open(); validate and restrict to allowed directories"),
    }

    for i, line in enumerate(lines, 1):
        for pattern, (issue, severity, cwe, rec) in path_traversal_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                findings["broken_access_control"].append({
                    "line":           i,
                    "content":        line.strip()[:80],
                    "issue":          issue,
                    "severity":       severity,
                    "owasp":          "A01:2025 - Broken Access Control",
                    "cwe":            cwe,
                    "recommendation": rec,
                })

    # ── SSRF Patterns (CWE-918) ──
    ssrf_patterns = {
        r'requests\.(get|post|put|delete)\s*\(.*\+':                                            ("SSRF — URL built by string concatenation passed to requests", "HIGH", "CWE-918", "Validate and allowlist URLs; use a URL parsing library to extract and check the hostname"),
        r'requests\.(get|post|put|delete)\s*\(\s*(?!["\'])\s*(?:request|args|form|GET|POST|params|input|user|query)[a-zA-Z0-9_.\[\]]*': ("SSRF risk — requests call with user-controlled URL", "MEDIUM", "CWE-918", "Validate URL origin against a strict allowlist before making external requests"),
        r'urllib\.request\.urlopen\s*\(.*(?:request\.|args\[|form\[|GET\[|POST\[|params\[|user_|input_)': ("SSRF risk — urlopen with user-controlled URL", "MEDIUM", "CWE-918", "Validate and allowlist the URL before opening"),
    }

    for i, line in enumerate(lines, 1):
        for pattern, (issue, severity, cwe, rec) in ssrf_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                findings["injection_vulnerabilities"].append({
                    "line":           i,
                    "content":        line.strip()[:80],
                    "issue":          issue,
                    "severity":       severity,
                    "owasp":          "A10:2025 - Server-Side Request Forgery (SSRF)",
                    "cwe":            cwe,
                    "recommendation": rec,
                })

    # ── CWE-20: Missing Input Validation ──
    if "def " in code_content:
        functions = re.findall(r"def\s+(\w+)\s*\((.*?)\):", code_content)
        for func_name, params in functions:
            clean_params = [
                p.strip().split(":")[0].split("=")[0].strip()
                for p in params.split(",")
                if p.strip() not in ("self", "cls", "*args", "**kwargs", "")
            ]
            if clean_params:
                if func_name.startswith("_"):
                    continue
                if any(func_name.startswith(p) for p in UTILITY_PREFIXES):
                    continue
                func_match = re.search(
                    rf"def\s+{re.escape(func_name)}\s*\(.*?\).*?(?=\ndef |\Z)",
                    code_content, re.DOTALL
                )
                if func_match:
                    body = func_match.group()
                    if len(body.strip().split("\n")) < 5:
                        continue
                    func_idx  = code_content.find(f"def {func_name}")
                    preceding = code_content[max(0, func_idx - 150):func_idx]
                    if re.search(r'@(app|router)\.(get|post|put|delete|patch)', preceding):
                        continue
                    has_validation = any(kw in body for kw in [
                        "isinstance(", "raise ValueError", "raise TypeError",
                        "if not ", "assert ", "validate(", "if len(",
                        "if type(", "pydantic", "Schema", "BaseModel",
                        "Field(", "validator",
                    ])
                    if not has_validation:
                        findings["missing_validation"].append({
                            "function":       func_name,
                            "issue":          f"Function '{func_name}' has no input validation",
                            "severity":       "MEDIUM",
                            "owasp":          "A05:2025 - Injection / A06:2025 - Insecure Design",
                            "cwe":            "CWE-20: Improper Input Validation",
                            "recommendation": f"Validate parameter(s): {', '.join(clean_params)}",
                        })

    # ── CWE-390: Missing Error Handling ──
    risky_ops = {
        "open(":           "File I/O",
        "requests.get":    "HTTP GET request",
        "requests.post":   "HTTP POST request",
        "requests.put":    "HTTP PUT request",
        "requests.delete": "HTTP DELETE request",
        "cursor.execute":  "Database query",
        "json.loads(":     "JSON parsing",
        ".connect(":       "Network connection",
        "subprocess.":     "Subprocess call",
        "os.remove(":      "File deletion",
        "shutil.":         "File system operation",
    }

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for op, label in risky_ops.items():
            if op in stripped:
                current_indent = len(line) - len(line.lstrip())
                func_start     = None
                for j in range(i - 2, -1, -1):
                    if (lines[j].strip().startswith("def ") or
                            lines[j].strip().startswith("async def ")):
                        func_start = j
                        break
                if func_start is None:
                    break
                context_lines = lines[func_start:i]
                in_try        = any("try:" in l or "try :" in l for l in context_lines)
                in_outer_try  = any(
                    ("try:" in l or "try :" in l) and
                    (len(l) - len(l.lstrip())) < current_indent
                    for l in context_lines
                )
                if not in_try and not in_outer_try:
                    findings["missing_error_handling"].append({
                        "line":           i,
                        "content":        stripped[:80],
                        "issue":          f"{label} without error handling",
                        "severity":       "HIGH",
                        "owasp":          "A10:2025 - Mishandling of Exceptional Conditions",
                        "cwe":            "CWE-390: Detection of Error Condition Without Action",
                        "recommendation": "Wrap in try/except with specific exception types and proper logging",
                    })
                break

    # ── Performance Issues ──
    loop_count = code_content.count("for ")
    if loop_count > 3:
        findings["performance_issues"].append({
            "issue":          f"High loop density ({loop_count} loops detected)",
            "severity":       "MEDIUM",
            "risk":           "Potential O(n²) or worse algorithmic complexity",
            "recommendation": "Use sets/dicts for lookups; consider pandas or vectorized operations",
        })

    if re.search(r'for .+\n.+\+=\s*["\']', code_content, re.MULTILINE):
        findings["performance_issues"].append({
            "issue":          "String concatenation inside a loop",
            "severity":       "MEDIUM",
            "risk":           "Each += creates a new string object — O(n²) memory behavior",
            "recommendation": "Collect strings in a list, then use ''.join(parts) after the loop",
        })

    if re.search(r'\.query\(', code_content) and "for " in code_content:
        findings["performance_issues"].append({
            "issue":          "Possible N+1 database query pattern",
            "severity":       "HIGH",
            "risk":           "Each loop iteration may fire a separate database query",
            "recommendation": "Use eager loading, JOIN queries, or batch fetching",
        })

    # ── Style Violations ──
    for i, line in enumerate(lines, 1):
        if len(line) > 100:
            findings["style_violations"].append({
                "line":     i,
                "issue":    f"Line too long ({len(line)} chars — PEP8 max is 79–100)",
                "severity": "LOW",
            })
        if "\t" in line:
            findings["style_violations"].append({
                "line":     i,
                "issue":    "Tab character found (PEP8 requires 4 spaces)",
                "severity": "LOW",
            })

    # ── Build Summary ──
    all_issues = [
        item
        for key in findings
        if key != "summary"
        for item in findings[key]
    ]

    findings["summary"] = {
        "total_issues": len(all_issues),
        "critical":     sum(1 for i in all_issues if i.get("severity") == "CRITICAL"),
        "high":         sum(1 for i in all_issues if i.get("severity") == "HIGH"),
        "medium":       sum(1 for i in all_issues if i.get("severity") == "MEDIUM"),
        "low":          sum(1 for i in all_issues if i.get("severity") == "LOW"),
    }

    return findings


# ─────────────────────────────────────────────
# TOOL 2: Deep engine scan (Semgrep)
# ─────────────────────────────────────────────


def run_deep_scan(code_content: str, language: str = "python") -> Dict:
    ext_map = {
        "python":     ".py",  "javascript": ".js",  "typescript": ".ts",
        "java":       ".java","go":          ".go",  "ruby":       ".rb",
        "php":        ".php", "rust":        ".rs",  "c":          ".c",
        "cpp":        ".cpp", "kotlin":      ".kt",
    }
    ext = ext_map.get(language.lower(), ".py")

    tmp_dir   = tempfile.mkdtemp(prefix="review_")
    temp_file = os.path.join(tmp_dir, f"code{ext}")

    rules_dir    = os.path.dirname(os.path.abspath(__file__))
    custom_rules = os.path.join(rules_dir, "ai_code_review.yaml")
    use_custom   = os.path.isfile(custom_rules)

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(code_content)

        cmd = [
            "semgrep", "scan",
            "--config", "p/owasp-top-ten",
            "--config", "p/cwe-top-25",
            "--config", "p/secrets",
            "--config", "p/security-audit",
        ]
        if use_custom:
            cmd += ["--config", custom_rules]
        cmd += ["--json", "--quiet", "--no-git-ignore", temp_file]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)

        formatted = []
        if result.stdout:
            try:
                data = json.loads(result.stdout)
                for r in data.get("results", []):
                    extra    = r.get("extra", {})
                    metadata = extra.get("metadata", {})

                    confidence = metadata.get("confidence", "MEDIUM").upper()
                    if confidence == "LOW":
                        continue

                    cwe_tags   = metadata.get("cwe",   [])
                    owasp_tags = metadata.get("owasp", [])
                    if isinstance(cwe_tags,   str): cwe_tags   = [cwe_tags]
                    if isinstance(owasp_tags, str): owasp_tags = [owasp_tags]

                    rule_id = r.get("check_id", "")
                    parts   = rule_id.split(".")
                    clean_category = " ".join(
                        p.replace("-", " ").replace("_", " ").title()
                        for p in parts[-2:]
                    ) if len(parts) >= 2 else rule_id.replace("-", " ").title()

                    formatted.append({
                        "category":    clean_category,
                        "severity":    extra.get("severity", "UNKNOWN").upper(),
                        "description": extra.get("message", "").strip(),
                        "line":        r.get("start", {}).get("line", "?"),
                        "end_line":    r.get("end",   {}).get("line", "?"),
                        "code":        extra.get("lines", "").strip(),
                        "cwe":         cwe_tags,
                        "owasp":       owasp_tags,
                        "fix":         extra.get("fix", None),
                        "confidence":  confidence,
                    })
            except json.JSONDecodeError:
                pass

        return {
            "findings_count":       len(formatted),
            "findings":             formatted,
            "custom_rules_applied": use_custom,
        }

    except FileNotFoundError:
        return {"findings_count": 0, "findings": [], "note": "Deep scanning engine not installed. Run: pip install semgrep"}
    except subprocess.TimeoutExpired:
        return {"findings_count": 0, "findings": [], "note": "Deep scan timed out — try a smaller code block"}
    except Exception as e:
        return {"findings_count": 0, "findings": [], "note": f"Deep scan unavailable: {type(e).__name__}"}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)