// EMO-X benchmark plugin for forge-agent (DeepSeek/Gemini CLI).
//
// Invokes the EMO-X harness (shared/run.py) as a subprocess and returns
// the sealed-bundle summary. Never invents numbers: every result comes
// from results/raw/RUN-ID/. Install: copy to ~/.deepseek-agent/tools/.
//
// Usage inside forge-agent:
//   emo_x(action="splash")                            hero splash screen
//   emo_x(action="self_test")                       harness check first
//   emo_x(action="run", suite="code25", trials=1)   code suite
//   emo_x(action="run", suite="profile", trials=3)  full profile
//   emo_x(action="health")                          benchmark health
//   emo_x(action="render", run_dir="results/raw/RUN-ID/")  HTML report
//     (prints the report.html path — open it in a browser)
//
// Rules enforced here (mirror SKILL.md): self_test before any run;
// hidden/security suites need explicit scope (fail-closed, never
// bypassed); results tagged NON-COMPARABLE against direct run.py rows.
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

// Set EMOX_ROOT to your emo-x checkout. No default path is baked in
// (a hardcoded path would leak the author's machine layout).
const EMOX = process.env.EMOX_ROOT || "";
const RUN_PY = EMOX ? path.join(EMOX, "shared", "run.py") : "";

const SUITES = ["code25", "dynamic-code", "recovery", "robustness",
  "calibration", "long-horizon", "gauntlet", "profile", "security"];

function runPy(args, cwd, script) {
  return new Promise((resolve, reject) => {
    const child = spawn("python3", [script || RUN_PY, ...args], {
      cwd: cwd || EMOX, shell: false, env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "", stderr = "";
    child.stdout.on("data", (c) => { stdout += c.toString(); });
    child.stderr.on("data", (c) => { stderr += c.toString(); });
    child.on("error", reject);
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}

function tailLines(s, n) {
  const lines = (s || "").trim().split("\n");
  return lines.slice(-n).join("\n");
}

module.exports = {
  name: "emo_x",
  description: "Run the EMO-X benchmark (execution-based model/agent evaluation). Actions: self_test, run, health. Reads sealed raw bundles only; never invents scores.",
  parameters: {
    action: { type: "string", required: true,
      description: "self_test | run | health" },
    suite: { type: "string", required: false,
      description: "code25 | dynamic-code | recovery | robustness | calibration | long-horizon | gauntlet | profile | security" },
    trials: { type: "number", required: false, description: "repeated trials (default 1)" },
    seed: { type: "number", required: false, description: "deterministic instance seed" },
    instances: { type: "number", required: false, description: "instances per family" },
    model: { type: "string", required: false, description: "MODEL-ID (or set OPENAI_MODEL)" },
    out: { type: "string", required: false, description: "results dir (default results/)" },
    run_dir: { type: "string", required: false, description: "raw bundle dir to render (render action)" },
  },

  async execute({ action, suite, trials, seed, instances, model, out, run_dir }) {
    if (!fs.existsSync(RUN_PY)) {
      return "emo_x misconfigured: shared/run.py not found. Set EMOX_ROOT to your emo-x checkout.";
    }
    if (action === "splash") {
      const r = await runPy([], EMOX,
        path.join(EMOX, "shared", "splash.py"));
      return r.code === 0 ? r.stdout : "Splash unavailable.";
    }
    if (action === "self_test") {
      const r = await runPy(["--self-test"]);
      return r.code === 0
        ? "EMO-X self-test PASS:\n" + tailLines(r.stdout, 16)
        : "EMO-X self-test FAILED (do not benchmark):\n" + tailLines(r.stdout + r.stderr, 20);
    }
    if (action === "health") {
      const r = await runPy(["--health"]);
      return tailLines(r.stdout, 30) || tailLines(r.stderr, 10);
    }
    if (action === "render") {
      if (!run_dir) return 'Pass run_dir, e.g. emo_x(action="render", run_dir="results/raw/RUN-ID/").';
      const base = String(run_dir).replace(/\/+$/, "").split("/").pop();
      const outDir = (out || "reports") + "/" + base;
      const r = await runPy([run_dir, "--out", outDir], EMOX,
        path.join(EMOX, "shared", "render_report.py"));
      if (r.code !== 0) return "Render failed:\n" + tailLines(r.stdout + r.stderr, 10);
      return "Report written to " + outDir + "/report.html — open it in a browser:\n" + outDir + "/report.html";
    }
    if (action === "run") {
      if (!suite || !SUITES.includes(suite)) {
        return "Unknown suite. Choose: " + SUITES.join(" | ");
      }
      if (suite === "security") {
        return "Refused: security suite needs explicit scope approval (EMOX_SCOPE_APPROVED=1 + EMOX_SCOPE_TARGET). Re-run inside a shell with approval, or use S1/S2 filters. Fail-closed by design.";
      }
      if (suite === "code25-hidden" || suite === "hidden") {
        return "Refused: hidden validation suite needs --hidden-ok opt-in. Never for public claims.";
      }
      // Gate: self-test must pass in this checkout before any run.
      const st = await runPy(["--self-test"]);
      if (st.code !== 0) {
        return "Refused: self-test fails — fix the harness first:\n" + tailLines(st.stdout + st.stderr, 12);
      }
      const args = ["--backend", "openai-generic", "--suite", suite,
        "--trials", String(trials || 1),
        "--out", out || "results/"];
      if (seed !== undefined) args.push("--seed", String(seed));
      if (instances !== undefined) args.push("--instances", String(instances));
      if (model) args.push("--model", model);
      const r = await runPy(args);
      const summary = tailLines(r.stdout, 8);
      return (r.code === 0 ? "EMO-X run done (NON-COMPARABLE vs direct run.py rows — tag host: forge-agent):\n" :
        "EMO-X run exited " + r.code + ":\n") + summary +
        "\nRead the sealed bundle under results/raw/RUN-*/ (manifest+events+responses+environment). Report profile+fingerprint+efficiency+uncertainty, never one number.";
    }
    return 'Unknown action. Use action="splash" | "self_test" | "run" | "health" | "render".';
  },
};
