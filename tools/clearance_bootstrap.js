#!/usr/bin/env node
/**
 * One-time Cloudflare clearance bootstrap for the sites that serve an interactive Turnstile.
 *
 * A normal browser window sidesteps the widget in a few seconds; the resulting
 * `cf_clearance` cookie is valid for the machine's IP, so Kodi can reuse it for ~24 hours.
 * This script drives a real Chrome (off-screen) over the DevTools protocol, waits until the
 * protected page answers HTTP 200 and writes the cookie into the add-on's profile as
 * `clearance_<site>.json` - exactly what `resources/lib/retro_stream_network.py` reads.
 *
 * Usage:
 *   node tools/clearance_bootstrap.js myclassicp
 *   node tools/clearance_bootstrap.js vintageworldp --profile "C:\...\plugin.video.adulthideout"
 *   node tools/clearance_bootstrap.js https://myclassicp.com/ --timeout 90
 *
 * Requires Node 21+ (global WebSocket) and a local Chrome or Edge. No npm packages.
 */
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { execFileSync, spawn } = require("node:child_process");

const SITES = {
    myclassicp: "https://myclassicp.com/",
    vintageworldp: "https://vintageworldp.com/",
};

const CHROME_CANDIDATES = [
    path.join(process.env.ProgramFiles || "C:\\Program Files", "Google", "Chrome", "Application", "chrome.exe"),
    path.join(process.env["ProgramFiles(x86)"] || "C:\\Program Files (x86)", "Google", "Chrome", "Application", "chrome.exe"),
    path.join(process.env.LOCALAPPDATA || "", "Google", "Chrome", "Application", "chrome.exe"),
    path.join(process.env.ProgramFiles || "C:\\Program Files", "Microsoft", "Edge", "Application", "msedge.exe"),
    path.join(process.env["ProgramFiles(x86)"] || "C:\\Program Files (x86)", "Microsoft", "Edge", "Application", "msedge.exe"),
];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function parseArgs(argv) {
    const args = { _: [] };
    for (let index = 0; index < argv.length; index += 1) {
        const item = argv[index];
        if (item === "--profile") args.profile = argv[++index];
        else if (item === "--timeout") args.timeout = Number(argv[++index]);
        else if (item === "--chrome") args.chrome = argv[++index];
        else if (item === "--keep-open") args.keepOpen = true;
        else args._.push(item);
    }
    return args;
}

function defaultProfile() {
    const appData = process.env.APPDATA;
    if (!appData) throw new Error("APPDATA is not set; pass --profile explicitly");
    return path.join(appData, "Kodi", "userdata", "addon_data", "plugin.video.adulthideout");
}

function findChrome(explicit) {
    if (explicit) {
        if (!fs.existsSync(explicit)) throw new Error("Chrome not found: " + explicit);
        return explicit;
    }
    for (const candidate of CHROME_CANDIDATES) {
        if (candidate && fs.existsSync(candidate)) return candidate;
    }
    throw new Error("No Chrome or Edge found; pass --chrome <path>");
}

function freePort() {
    return 9300 + Math.floor(Math.random() * 400);
}

async function cdpBase(port, deadline) {
    for (;;) {
        for (const host of ["[::1]", "127.0.0.1"]) {
            try {
                const reply = await fetch(`http://${host}:${port}/json/version`);
                if (reply.ok) return `http://${host}:${port}`;
            } catch (err) {
                /* not up yet */
            }
        }
        if (Date.now() > deadline) throw new Error("Chrome DevTools did not answer");
        await sleep(250);
    }
}

class Cdp {
    constructor(wsUrl) {
        this.nextId = 1;
        this.pending = new Map();
        this.documents = [];
        this.ws = new WebSocket(wsUrl);
        this.ready = new Promise((resolve, reject) => {
            this.ws.onopen = () => resolve();
            this.ws.onerror = (err) => reject(new Error("websocket error: " + (err && err.message)));
        });
        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            if (message.id && this.pending.has(message.id)) {
                const { resolve, reject } = this.pending.get(message.id);
                this.pending.delete(message.id);
                if (message.error) reject(new Error(JSON.stringify(message.error)));
                else resolve(message.result);
            } else if (message.method === "Network.responseReceived" && message.params.type === "Document") {
                this.documents.push({ url: message.params.response.url, status: message.params.response.status });
            }
        };
    }
    async send(method, params = {}) {
        await this.ready;
        const id = this.nextId++;
        const promise = new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
        this.ws.send(JSON.stringify({ id, method, params }));
        return promise;
    }
    close() { try { this.ws.close(); } catch (err) { /* ignore */ } }
}

async function evaluate(cdp, expression) {
    const result = await cdp.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    return result.result ? result.result.value : undefined;
}

const CHALLENGE_TITLES = ["just a moment", "nur einen moment", "einen moment", "attention required", "checking your browser"];
const STEALTH = `
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = window.chrome || { runtime: {}, loadTimes: () => ({}), csi: () => ({}) };
`;

async function solve(url, timeoutSeconds, chromePath) {
    const port = freePort();
    const userDataDir = path.join(os.tmpdir(), "clearance-bootstrap-" + Date.now());
    const chrome = spawn(chromePath, [
        "--remote-debugging-port=" + port,
        "--user-data-dir=" + userDataDir,
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "--window-position=-3200,-3200",
        "--window-size=1000,800",
        "about:blank",
    ], { stdio: "ignore", detached: false });

    try {
        const base = await cdpBase(port, Date.now() + 20000);
        const created = await fetch(`${base}/json/new?${encodeURIComponent("about:blank")}`, { method: "PUT" }).then((r) => r.json());
        const cdp = new Cdp(created.webSocketDebuggerUrl);
        try {
            await cdp.send("Network.enable");
            await cdp.send("Page.enable");
            await cdp.send("Runtime.enable");
            await cdp.send("Page.addScriptToEvaluateOnNewDocument", { source: STEALTH });
            await cdp.send("Page.navigate", { url });

            const deadline = Date.now() + timeoutSeconds * 1000;
            let title = "";
            let lastStatus = null;
            while (Date.now() < deadline) {
                await sleep(2000);
                title = String(await evaluate(cdp, "document.title") || "");
                const docs = cdp.documents.filter((entry) => entry.url.includes(new URL(url).host));
                lastStatus = docs.length ? docs[docs.length - 1].status : null;
                const waiting = CHALLENGE_TITLES.some((marker) => title.toLowerCase().includes(marker));
                if (!waiting && lastStatus === 200) break;
            }

            const cookieResult = await cdp.send("Network.getCookies", { urls: [url] });
            const cookies = {};
            for (const cookie of cookieResult.cookies || []) cookies[cookie.name] = cookie.value;
            const userAgent = await evaluate(cdp, "navigator.userAgent");
            const bodyLength = await evaluate(cdp, "document.body ? document.body.innerHTML.length : -1");
            return { title, status: lastStatus, cookies, userAgent, bodyLength, documents: cdp.documents };
        } finally {
            cdp.close();
            await fetch(`${base}/json/close/${created.id}`).catch(() => null);
        }
    } finally {
        if (!process.env.CLEARANCE_KEEP_CHROME) {
            try { execFileSync("taskkill", ["/PID", String(chrome.pid), "/T", "/F"], { stdio: "ignore" }); }
            catch (err) { try { chrome.kill("SIGKILL"); } catch (ignored) { /* ignore */ } }
            await sleep(500);
            try { fs.rmSync(userDataDir, { recursive: true, force: true }); } catch (err) { /* ignore */ }
        }
    }
}

async function main() {
    const args = parseArgs(process.argv.slice(2));
    const requested = args._[0];
    if (!requested) {
        console.error("usage: node tools/clearance_bootstrap.js <" + Object.keys(SITES).join("|") + "|url> [--profile DIR] [--timeout SECONDS]");
        process.exit(2);
    }
    const url = SITES[requested] || (requested.startsWith("http") ? requested : null);
    if (!url) throw new Error("Unknown site: " + requested + " (known: " + Object.keys(SITES).join(", ") + ")");

    const host = new URL(url).hostname;
    const siteId = host.replace(/^www\./, "").split(".")[0];
    const profileDir = args.profile || defaultProfile();
    const chromePath = findChrome(args.chrome);
    const timeout = args.timeout || 75;

    console.log(`Solving ${url} with ${path.basename(chromePath)} (timeout ${timeout}s) ...`);
    const result = await solve(url, timeout, chromePath);
    const clearance = result.cookies.cf_clearance;

    console.log(`page: "${result.title}" HTTP ${result.status}, body ${result.bodyLength} bytes`);
    if (!clearance) {
        console.error("No cf_clearance cookie was issued - the challenge did not pass.");
        process.exit(1);
    }

    fs.mkdirSync(profileDir, { recursive: true });
    const target = path.join(profileDir, `clearance_${siteId}.json`);
    const record = {
        cookies: result.cookies,
        domain: "." + host.replace(/^www\./, "").split(".").slice(-2).join("."),
        ua: result.userAgent || "",
        ts: Date.now() / 1000,
    };
    fs.writeFileSync(target, JSON.stringify(record, null, 2), "utf8");
    console.log(`wrote ${target}`);
    console.log("cookies: " + Object.keys(result.cookies).join(", ") + ` (clearance ${String(clearance).length} chars)`);
    console.log("Valid for about 24 hours for this IP; rerun when a site asks for the challenge again.");
}

main().catch((err) => {
    console.error("FAILED: " + (err && err.message ? err.message : err));
    process.exit(1);
});
