export type Domain = "rate_limiter" | "handover" | "generic";

export interface ParsedSpec {
  title: string;
  domain: Domain;
  body: string;
  headings: string[];
  requirements: string[];
  failureModes: string[];
  numbers: Record<string, number>;
  adminKeys: string[];
  actions: string[];
}

const DOMAIN_HINTS: Record<Exclude<Domain, "generic">, string[]> = {
  rate_limiter: [
    "rate limit",
    "rate-limit",
    "token-bucket",
    "token bucket",
    "retry-after",
    "burst",
    "rps",
    "quota",
    "429",
    "api key",
  ],
  handover: [
    "handover",
    "hand-over",
    "a3",
    "rsrp",
    "rsrq",
    "ttt",
    "hysteresis",
    "ping-pong",
    "radio link",
    "neighbor cell",
    "serving cell",
  ],
};

export function parseSpec(text: string): ParsedSpec {
  const body = text.trim();
  const domain = detectDomain(body);
  return {
    title: extractTitle(body),
    domain,
    body,
    headings: Array.from(body.matchAll(/^#{2,3}\s+(.+)$/gm), (match) => match[1]),
    requirements: extractRequirements(body),
    failureModes: extractFailureModes(body),
    numbers: extractNumbers(body, domain),
    adminKeys: extractAdminKeys(body),
    actions: extractActions(body),
  };
}

export function detectDomain(text: string): Domain {
  const lowered = text.toLowerCase();
  const scores = (Object.keys(DOMAIN_HINTS) as Array<Exclude<Domain, "generic">>).map((domain) => ({
    domain,
    score: DOMAIN_HINTS[domain].reduce((sum, hint) => sum + (lowered.includes(hint) ? 1 : 0), 0),
  }));
  scores.sort((a, b) => b.score - a.score);
  return scores[0].score >= 2 ? scores[0].domain : "generic";
}

function extractTitle(text: string): string {
  const match = text.match(/^#\s+(.+)$/m);
  if (match) return match[1].trim();
  const first = text.split("\n")[0]?.trim() ?? "Untitled Specification";
  return first.replace(/^#\s*/, "").trim() || "Untitled Specification";
}

function extractRequirements(text: string): string[] {
  const items: string[] = [];
  for (const match of text.matchAll(/^\s*(?:\d+[.)]|[-*])\s+(.+)$/gm)) {
    const line = match[1].trim();
    if (line.length >= 12) items.push(line.replace(/\s+/g, " "));
  }
  for (const match of text.matchAll(/((?:shall|must|must not|may not)\b[^.\n]{8,160})/gi)) {
    const clause = match[1].trim().replace(/\s+/g, " ");
    if (!items.includes(clause)) items.push(clause);
  }
  return items.slice(0, 40);
}

function extractFailureModes(text: string): string[] {
  const block = text.match(/(?:failure modes|failure-mode)[^\n]*\n((?:[-*]\s+.+\n?)+)/i);
  if (!block) return [];
  return Array.from(block[1].matchAll(/[-*]\s+(.+)/g), (match) => match[1].trim().replace(/\s+/g, " "));
}

function extractAdminKeys(text: string): string[] {
  const keys = Array.from(text.toLowerCase().matchAll(/`([a-z0-9][a-z0-9\-_]{2,32})`/g), (match) => match[1]);
  const preferred = keys.filter(
    (key) => ["ops", "root", "noc", "pager"].some((token) => key.includes(token)) || (key.startsWith("admin") && !key.includes("bypass")),
  );
  return Array.from(new Set(preferred.length ? preferred : ["ops-root", "noc-pager"]));
}

function extractActions(text: string): string[] {
  const match = text.match(/action[^\n]*\n((?:\s*[-*]\s+`.+`[^\n]*\n?)+)/i);
  if (!match) return ["stay", "prepare", "execute", "complete", "rollback", "rlf"];
  const found = Array.from(match[1].matchAll(/`([a-z_]+)`/g), (item) => item[1].toLowerCase());
  return found.length ? found : ["stay", "prepare", "execute", "complete", "rollback", "rlf"];
}

function extractNumbers(text: string, domain: Domain): Record<string, number> {
  const lowered = text.toLowerCase();
  const numbers: Record<string, number> = {};

  function grab(key: string, patterns: RegExp[], fallback: number) {
    for (const pattern of patterns) {
      const match = lowered.match(pattern);
      if (match) {
        numbers[key] = Number.parseFloat(match[1].replace(/,/g, ""));
        return;
      }
    }
    numbers[key] = fallback;
  }

  if (domain === "rate_limiter") {
    grab("sustained_rps", [/(\d+(?:\.\d+)?)\s*(?:requests per second|rps|token\/s)/], 100);
    grab("burst", [/burst(?: capacity)?[^\d]{0,40}(\d+)/, /\*\*(\d+)\s+tokens\*\*/], 25);
    grab("daily_quota", [/daily quota[^\d]{0,40}(\d[\d,]*)/, /\*\*daily quota of ([0-9,]+)\*\*/], 100000);
    grab("max_keys", [/(?:at most|track at most)\s+\*\*(\d[\d,]*)/, /(\d[\d,]*)\s+concurrent api keys/], 1000);
    grab("idle_ms", [/(\d+)\s*ms of idle/], 250);
  } else if (domain === "handover") {
    grab("hysteresis_db", [/hysteresis[^\d]{0,20}(\d+(?:\.\d+)?)/, /hys[^\d]{0,16}(\d+(?:\.\d+)?)/], 3.0);
    grab("a3_offset_db", [/a3 offset[^\d]{0,24}(\d+(?:\.\d+)?)/, /off\)[^\d]{0,12}(\d+(?:\.\d+)?)/], 2.0);
    grab("ttt_ms", [/ttt[^\d]{0,16}(\d+)/, /ttt = \*\*(\d+)/], 320);
    grab("ping_pong_ms", [/for \*\*(\d+)\s*ms\*\*/, /ping-pong[^\d]{0,48}(\d+)/], 2000);
    grab("rlf_rsrp", [/(?:below|strictly below)\s+\*\*(-?\d+(?:\.\d+)?)/, /strictly below\s+(-?\d+(?:\.\d+)?)/], -110);
    grab("max_neighbors", [/at most\s+\*\*(\d+)\*\*\s+neighbor/, /at most\s+(\d+)\s+neighbor/], 3);
  } else {
    grab("timeout_ms", [/(\d+)\s*ms/], 1000);
    grab("limit", [/(?:limit|max(?:imum)?|at most)\s+(\d[\d,]*)/], 100);
  }
  return numbers;
}

export function intNum(numbers: Record<string, number>, key: string, fallback: number): number {
  const value = numbers[key];
  return Number.isFinite(value) ? Math.trunc(value) : fallback;
}

export function py(value: unknown): string {
  return JSON.stringify(value);
}
