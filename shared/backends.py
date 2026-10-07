"""EMO-X backends — one chat() interface (PROMPT_PACK v1).

Backends: kaggle | colab | openai-generic. Stdlib only (urllib).

Config (env-driven, explicit args win):
  kaggle / colab : BASE_URL + MODEL  (also accepts AGENT_BASE / AGENT_MODEL)
  openai-generic : OPENAI_BASE_URL (+ OPENAI_API_KEY / OPENAI_KEY) + OPENAI_MODEL
                   (falls back to BASE_URL / MODEL when OPENAI_* unset,
                    so local vLLM / Ollama OpenAI-compat endpoints work)

One interface:
  chat = make_chat(backend, base_url, model, api_key)
  text, secs, usage = chat(messages, temp=0.4, max_tokens=512,
                           think=None, num_predict=None)

Routing rule (documented, frozen):
  - think is None and num_predict is None -> OpenAI-compatible
    POST {base}/chat/completions
  - think or num_predict given -> Ollama native POST {base}/api/chat
    (base '/v1' suffix stripped). Carries `think` flag + num_predict support.
    Math tests (H1-H3) MUST use think=False via this path (PROMPT_PACK v1).

Capability manifests (SPEC 36): see CAPABILITY_FIELDS /
get_capability_manifest() / comparability() below. `/v1/chat/completions`
compatibility does NOT imply equal token counting, reasoning, tool calling,
streaming, stop behavior, seed, or max-tokens semantics across providers.
"""

import json
import ipaddress
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 300

#: Extra hostnames always refused (metadata service aliases). IP-range
#: classification for resolved addresses lives in _validate_base_url.
_BLOCKED_HOSTS = frozenset(("metadata.google.internal",))

#: Networks that are never acceptable for a model base URL unless
#: EMOX_ALLOW_LOCAL=1 (SSRF defense-in-depth). Covers loopback, RFC1918,
#: link-local (cloud metadata), CGNAT, reserved, multicast, unspecified,
#: and IPv4-mapped IPv6.
_FORBIDDEN_NETS = tuple(
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "224.0.0.0/4",
        "240.0.0.0/4",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
        "::ffff:0:0/96",
    )
)


def _ip_is_forbidden(ip_text):
    """True iff an IP string falls in a non-public network."""
    try:
        ip = ipaddress.ip_address(ip_text)
    except ValueError:
        return True  # unparseable -> fail closed
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return True
    for net in _FORBIDDEN_NETS:
        if ip.version == net.version and ip in net:
            return True
    return False


def _validate_base_url(base_url):
    """Reject base URLs resolving to non-public IPs unless EMOX_ALLOW_LOCAL=1.

    Resolves the hostname and classifies every returned address, so
    textual aliases (127.1, decimal/hex IPv4, IPv4-mapped IPv6, internal
    DNS names) cannot bypass the guard. Unresolvable hosts (NXDOMAIN)
    are allowed through deliberately: DNS is not the SSRF control, the
    resolved-IP classification is; a rebinding hostname resolves (to a
    private IP) and is still blocked, and an NXDOMAIN host cannot
    connect anyway. Raises ValueError; returns URL unchanged when allowed.
    """
    if os.environ.get("EMOX_ALLOW_LOCAL") == "1":
        return base_url
    try:
        parts = urllib.parse.urlsplit(base_url or "")
        host = parts.hostname or ""
        port = parts.port
    except Exception:
        host, port = "", None
    if not host:
        raise ValueError("base URL has no host: %r" % (base_url,))
    if host.lower() in _BLOCKED_HOSTS:
        raise ValueError(
            "refusing base URL host %r (metadata alias); "
            "set EMOX_ALLOW_LOCAL=1 to allow local endpoints" % host
        )
    try:
        infos = socket.getaddrinfo(host, port or None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        # Unresolvable host: allow through. DNS is not the SSRF control
        # here; the resolved-IP classification below is. A rebinding
        # hostname resolves (to a private IP) and is still blocked, and
        # an NXDOMAIN host cannot connect anyway. Failing closed here
        # would break legitimate offline/test environments.
        return base_url
    for info in infos:
        ip_text = info[4][0]
        if _ip_is_forbidden(ip_text):
            raise ValueError(
                "refusing base URL host %r resolving to non-public %s; "
                "set EMOX_ALLOW_LOCAL=1 to allow local endpoints" % (host, ip_text)
            )
    return base_url


def _strip_slash(u):
    return (u or "").rstrip("/")


def _redact_host(url):
    """Return a log-safe host label for a URL (never includes userinfo).

    Used in error messages so connection failures cannot echo embedded
    credentials. Returns the hostname (plus port when present), or the
    input unchanged when it does not parse.
    """
    try:
        parts = urllib.parse.urlsplit(url or "")
        host = parts.hostname or ""
        if not host:
            return "[unparseable-url]"
        if parts.port:
            return "%s:%d" % (host, parts.port)
        return host
    except Exception:
        return "[unparseable-url]"


def resolve_config(backend="kaggle", base_url=None, model=None, api_key=None):
    """Resolve (base_url, model, api_key) from args then env. Raises ValueError."""
    backend = (backend or os.environ.get("BACKEND", "kaggle")).lower()
    if backend in ("kaggle", "colab"):
        base = base_url or os.environ.get("BASE_URL") or os.environ.get("AGENT_BASE")
        mod = model or os.environ.get("MODEL") or os.environ.get("AGENT_MODEL")
        key = api_key  # tunnels need no key
    elif backend in ("openai-generic", "openai_generic", "openai"):
        base = base_url or os.environ.get("OPENAI_BASE_URL") or os.environ.get("BASE_URL")
        mod = model or os.environ.get("OPENAI_MODEL") or os.environ.get("MODEL")
        key = (
            api_key
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("OPENAI_KEY")
            or os.environ.get("KEY")
        )
        backend = "openai-generic"
    elif backend == "cli":
        # Local CLI harness: base doubles as the binary (path or PATH
        # name), model is the CLI route id (e.g. opencode/<route>).
        base = base_url or os.environ.get("CLI_BIN") or os.environ.get("BASE_URL") or "opencode"
        mod = model or os.environ.get("CLI_MODEL") or os.environ.get("MODEL")
        key = None  # auth lives in the CLI's own config, never here
    else:
        raise ValueError("unknown backend: %r (kaggle|colab|openai-generic|cli)" % backend)
    if not base:
        raise ValueError("missing base URL (pass --base-url or set BASE_URL)")
    if not mod:
        raise ValueError("missing model (pass --model or set MODEL)")
    # The cli backend's `base` is a local binary path, not a network URL:
    # SSRF validation is meaningless (and would reject /bin/echo). Skip it.
    if backend != "cli":
        _validate_base_url(base)
    return backend, _strip_slash(base), mod, key


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Fail-closed redirect handler for model endpoints (P0-3).

    urllib follows 301/302 by default without re-validating the target,
    which would bypass _validate_base_url entirely. Refuse cross-host
    and private-IP redirects here instead.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            target = urllib.parse.urljoin(req.full_url, newurl)
            _validate_base_url(target)
        except ValueError as e:
            raise urllib.error.URLError("refusing redirect to non-public URL: %s" % e) from e
        return None


def _post_json(url, payload, api_key=None, timeout=TIMEOUT):
    # Audit M: never send a Bearer key over cleartext http to a
    # non-local endpoint (localhost http is the Ollama/test convention).
    if api_key:
        try:
            _p = urllib.parse.urlsplit(url or "")
            _local = (_p.hostname or "") in ("localhost", "127.0.0.1", "::1")
            if _p.scheme == "http" and not _local:
                raise RuntimeError(
                    "refusing to send credentials over http to %s" % _redact_host(url)
                )
        except RuntimeError:
            raise
        except Exception:
            pass
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(url, data=data, headers=headers)
    t0 = time.time()
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as r:
            body = json.load(r)
    except urllib.error.HTTPError as e:
        # Re-raise without the response body: error surfaces carry the
        # status code and (redacted) host only, never backend output
        # that could echo credentials or prompt content.
        raise RuntimeError("HTTP error %s for %s" % (getattr(e, "code", "?"), _redact_host(url)))
    except urllib.error.URLError as e:
        raise RuntimeError(
            "connection failed for %s: %s" % (_redact_host(url), getattr(e, "reason", e))
        )
    return body, round(time.time() - t0, 1)


def chat_openai_compatible(
    messages, base_url, model, api_key=None, temp=0.4, max_tokens=512, timeout=TIMEOUT
):
    """OpenAI-compatible chat. Returns (text, secs, usage)."""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temp,
        "stream": False,
        "max_tokens": max_tokens,
    }
    body, secs = _post_json(_strip_slash(base_url) + "/chat/completions", payload, api_key, timeout)
    text = body["choices"][0]["message"]["content"] or ""
    return text, secs, body.get("usage", {})


def chat_native(messages, base_url, model, temp=0.4, num_predict=600, think=False, timeout=TIMEOUT):
    """Ollama native chat (think flag + num_predict). Returns (text, secs, usage).

    Native URL derives from base by stripping a trailing '/v1'.
    think=False is REQUIRED for math tests H1-H3 (PROMPT_PACK v1).
    """
    base = _strip_slash(base_url)
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": think,
        "options": {"temperature": temp, "num_predict": num_predict},
    }
    body, secs = _post_json(base + "/api/chat", payload, None, timeout)
    text = (body.get("message") or {}).get("content") or ""
    return text, secs, {"eval": body.get("eval_count")}


def chat_cli(messages, cli_bin, model, timeout=TIMEOUT):
    """Single-turn chat via a local agent CLI subprocess. No shell.

    Builds `[bin, "run", "--model", route, prompt]` as an argv list
    (never a shell string). Strips ANSI codes and `>` status lines the
    CLI prints around the reply. Returns (text, secs, {}). Usage is
    unknown on this path (SPEC 36 conservative manifest).
    Raises RuntimeError on timeout / spawn failure / nonzero exit.
    """
    import re
    import shutil
    import subprocess

    exe = cli_bin if os.path.isfile(str(cli_bin)) else shutil.which(str(cli_bin))
    if not exe:
        raise RuntimeError("cli backend binary not found: %r" % (cli_bin,))
    prompt = "\n".join(
        "%s: %s" % (m.get("role", "user"), m.get("content", "")) for m in (messages or [])
    )
    argv = [exe, "run", "--model", model, prompt]
    try:
        timeout = int(os.environ.get("CLI_TIMEOUT", str(timeout)))
    except ValueError:
        pass
    t0 = time.time()
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("cli backend timeout after %ds: %s" % (timeout, model)) from e
    except OSError as e:
        raise RuntimeError("cli backend spawn failed: %s" % e) from e
    if p.returncode != 0:
        tail = ((p.stdout or "") + (p.stderr or ""))[-300:]
        raise RuntimeError("cli backend exit %d: %s" % (p.returncode, tail))
    text = re.sub(r"\x1b\[[0-9;]*m", "", p.stdout or "")
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith(">")]
    return "\n".join(lines).strip(), round(time.time() - t0, 1), {}


def make_chat(
    backend="kaggle",
    base_url=None,
    model=None,
    api_key=None,
    default_max_tokens=512,
    default_num_predict=600,
):
    """Build one chat() callable hiding backend differences.

    chat(messages, temp=0.4, max_tokens=512, think=None, num_predict=None):
      think/num_predict None -> OpenAI-compatible endpoint;
      otherwise             -> Ollama native endpoint (think flag honored).
    """
    name, base, mod, key = resolve_config(backend, base_url, model, api_key)

    def chat(messages, temp=0.4, max_tokens=None, think=None, num_predict=None):
        mt = max_tokens if max_tokens is not None else default_max_tokens
        if name == "cli":
            return chat_cli(messages, base, mod)
        if think is None and num_predict is None:
            kw = {} if name == "openai-generic" else {}
            return chat_openai_compatible(messages, base, mod, key, temp=temp, max_tokens=mt, **kw)
        return chat_native(
            messages,
            base,
            mod,
            temp=temp,
            num_predict=(num_predict if num_predict is not None else default_num_predict),
            think=False if think is None else think,
        )

    return chat


def get_default_chat():
    """chat() from environment only: BACKEND (+BASE_URL/MODEL or OPENAI_*)."""
    backend = os.environ.get("BACKEND", "kaggle")
    return make_chat(backend)


# ================= capability manifests (SPEC 36) =================
# A shared path (/v1/chat/completions) is not a shared behavior contract.
# Every backend therefore exposes what the harness+endpoint combination can
# actually do, so the leaderboard never mistakes API differences for model
# quality. Vocabulary per field is closed; anything unverified is "unknown".

CAPABILITY_FIELDS = (
    "chat",  # supported|unsupported
    "streaming",  # supported|unsupported  (harness always uses stream:false)
    "tool_calls",  # native|emulated|unsupported|unknown (provider-side tool use)
    "reasoning_tokens",  # supported|unsupported|unknown
    "seed",  # supported|unsupported|unknown (deterministic sampling)
    "token_usage",  # exact|estimated|unknown
    "vision",  # supported|unsupported|unknown (image input parts)
    "stop_behavior",  # supported|unsupported|unknown (stop sequences honored)
    "max_tokens",  # enforced|approximate|unknown
)

# Fields whose mismatch (or unknown) can shift scores. Differences outside
# this set never change comparability on their own.
MATERIAL_FIELDS = frozenset(
    (
        "tool_calls",
        "reasoning_tokens",
        "seed",
        "token_usage",
        "vision",
        "stop_behavior",
        "max_tokens",
    )
)

_UNKNOWN = "unknown"

# kaggle/colab = Ollama tunnel: native /api/chat path available, usage comes
# from eval_count (estimated), no seed/stop/vision/tool wire support.
_OLLAMA_TUNNEL = {
    "chat": "supported",
    "streaming": "unsupported",
    "tool_calls": "unsupported",
    "reasoning_tokens": "supported",
    "seed": "unsupported",
    "token_usage": "estimated",
    "vision": "unsupported",
    "stop_behavior": "unsupported",
    "max_tokens": "approximate",
}

BACKEND_CAPABILITIES = {
    "kaggle": dict(_OLLAMA_TUNNEL),
    "colab": dict(_OLLAMA_TUNNEL),
    # cli: local agent-CLI subprocess (e.g. `opencode run --model ROUTE`).
    # Conservative: no seed passthrough, no usage accounting, single-turn
    # text only. Equal routes on different CLIs are NOT equal backends.
    "cli": {
        "chat": "supported",
        "streaming": "unsupported",
        "tool_calls": "unsupported",
        "reasoning_tokens": "unknown",
        "seed": "unsupported",  # harness never sends seed on this path
        "token_usage": "unknown",
        "vision": "unsupported",
        "stop_behavior": "unknown",
        "max_tokens": "approximate",
    },
}

# openai-generic covers many providers behind one path. Default is the
# conservative "unknown" profile: never claim what was not verified.
# A named profile asserts verified provider behavior for that endpoint.
PROVIDER_PROFILES = {
    "unknown": {
        "chat": "supported",
        "streaming": "unsupported",
        "tool_calls": "unknown",
        "reasoning_tokens": "unknown",
        "seed": "unsupported",  # harness never sends seed on this path
        "token_usage": "unknown",
        "vision": "unknown",
        "stop_behavior": "unknown",
        "max_tokens": "unknown",
    },
    "openai": {
        "chat": "supported",
        "streaming": "unsupported",
        "tool_calls": "native",
        "reasoning_tokens": "supported",
        "seed": "unsupported",
        "token_usage": "exact",
        "vision": "supported",
        "stop_behavior": "supported",
        "max_tokens": "enforced",
    },
    "openrouter": {
        "chat": "supported",
        "streaming": "unsupported",
        "tool_calls": "native",
        "reasoning_tokens": "unknown",
        "seed": "unsupported",
        "token_usage": "estimated",
        "vision": "unknown",
        "stop_behavior": "supported",
        "max_tokens": "approximate",
    },
    "deepseek": {
        "chat": "supported",
        "streaming": "unsupported",
        "tool_calls": "native",
        "reasoning_tokens": "supported",
        "seed": "unsupported",
        "token_usage": "exact",
        "vision": "unsupported",
        "stop_behavior": "supported",
        "max_tokens": "enforced",
    },
    "vllm": {
        "chat": "supported",
        "streaming": "unsupported",
        "tool_calls": "native",
        "reasoning_tokens": "unknown",
        "seed": "supported",
        "token_usage": "exact",
        "vision": "unknown",
        "stop_behavior": "supported",
        "max_tokens": "enforced",
    },
    "ollama": dict(_OLLAMA_TUNNEL),
}


def get_capability_manifest(backend="kaggle", provider_profile=None):
    """Return the capability manifest for a backend (+profile). SPEC 36.

    backend: kaggle | colab | openai-generic.
    provider_profile (openai-generic only): one of PROVIDER_PROFILES;
      defaults to "unknown" (conservative). Unknown backend profiles raise
      ValueError; unknown providers fall back to "unknown", never to a
      permissive guess.
    """
    name = (backend or "kaggle").lower().replace("_", "-")
    if name in BACKEND_CAPABILITIES:
        manifest = dict(BACKEND_CAPABILITIES[name])
        manifest["backend"] = name
        manifest["provider_profile"] = "native"
        return manifest
    if name == "openai-generic":
        profile = (provider_profile or "unknown").lower()
        if profile not in PROVIDER_PROFILES:
            profile = "unknown"
        manifest = dict(PROVIDER_PROFILES[profile])
        manifest["backend"] = name
        manifest["provider_profile"] = profile
        return manifest
    raise ValueError("unknown backend for capability manifest: %r" % backend)


def comparability(man_a, man_b):
    """Compare two capability manifests. SPEC 36.

    Returns (verdict, reason) with verdict in:
      DIRECT — all material fields equal and none unknown.
      CONDITIONALLY_COMPARABLE — equal except unknown(s), or differences
        only outside MATERIAL_FIELDS.
      NON_COMPARABLE — a material supported-vs-otherwise conflict.
    """
    for field in CAPABILITY_FIELDS:
        a, b = man_a.get(field), man_b.get(field)
        if a == b:
            continue
        if field not in MATERIAL_FIELDS:
            return ("CONDITIONALLY_COMPARABLE", "immaterial difference in %r" % field)
        if _UNKNOWN in (a, b):
            return ("CONDITIONALLY_COMPARABLE", "unverified capability %r" % field)
        return ("NON_COMPARABLE", "material conflict in %r: %r vs %r" % (field, a, b))
    if any(man_a.get(f) == _UNKNOWN for f in MATERIAL_FIELDS):
        return ("CONDITIONALLY_COMPARABLE", "unverified material capability")
    return ("DIRECT", "identical material capabilities")


# ================= reasoning mode (SPEC 37, Y-5) ======================
# Every attempt records how reasoning was configured for the chat call
# that produced it. Vocabulary is closed (SPEC 37); validation of the
# field itself is owned by Y-1 (shared/schemas.py) — this function only
# PRODUCES valid values.


def reasoning_mode_for(think=None, num_predict=None, native_transport=False):
    """Map chat-call kwargs to a SPEC 37 reasoning mode. Y-5 contract.

    think True  -> "enabled"           (explicit reasoning requested)
    think False -> "disabled"          (reasoning explicitly switched off)
    native transport without a think flag (num_predict given or
      native_transport True) -> "native"
    plain OpenAI-compatible path (both None, not native)
      -> "provider_default"
    """
    if think is True:
        return "enabled"
    if think is False:
        return "disabled"
    if num_predict is not None or native_transport:
        return "native"
    return "provider_default"
