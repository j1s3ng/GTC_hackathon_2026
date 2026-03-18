const FEDERAL_DB_PATH = "../data/federal_resources.json";
const STATE_DB_PATH = (stateCode) => `../data/states/${stateCode.toLowerCase()}.json`;

const STATE_NAMES = {
  AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California",
  CO: "Colorado", CT: "Connecticut", DE: "Delaware", FL: "Florida", GA: "Georgia",
  HI: "Hawaii", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa",
  KS: "Kansas", KY: "Kentucky", LA: "Louisiana", ME: "Maine", MD: "Maryland",
  MA: "Massachusetts", MI: "Michigan", MN: "Minnesota", MS: "Mississippi", MO: "Missouri",
  MT: "Montana", NE: "Nebraska", NV: "Nevada", NH: "New Hampshire", NJ: "New Jersey",
  NM: "New Mexico", NY: "New York", NC: "North Carolina", ND: "North Dakota", OH: "Ohio",
  OK: "Oklahoma", OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island", SC: "South Carolina",
  SD: "South Dakota", TN: "Tennessee", TX: "Texas", UT: "Utah", VT: "Vermont",
  VA: "Virginia", WA: "Washington", WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming",
};

const ZIP3_STATE_RANGES = {
  AL: [[350, 369]], AK: [[995, 999]], AZ: [[850, 853], [855, 857], [859, 865]], AR: [[716, 729]],
  CA: [[900, 908], [910, 918], [919, 925], [926, 928], [930, 939], [940, 961]], CO: [[800, 816]],
  CT: [[60, 69]], DE: [[197, 199]], FL: [[320, 339], [341, 342], [344, 344], [346, 347], [349, 349]],
  GA: [[300, 319], [398, 399]], HI: [[967, 968]], ID: [[832, 838]], IL: [[600, 629]],
  IN: [[460, 479]], IA: [[500, 528]], KS: [[660, 679]], KY: [[400, 427]], LA: [[700, 714]],
  ME: [[39, 49]], MD: [[206, 219]], MA: [[10, 27], [55, 55]], MI: [[480, 499]],
  MN: [[550, 567]], MS: [[386, 397]], MO: [[630, 658]], MT: [[590, 599]], NE: [[680, 693]],
  NV: [[889, 898]], NH: [[30, 38]], NJ: [[70, 89]], NM: [[870, 884]], NY: [[5, 5], [100, 149]],
  NC: [[270, 289]], ND: [[580, 588]], OH: [[430, 459]], OK: [[730, 731], [734, 749]], OR: [[970, 979]],
  PA: [[150, 196]], RI: [[28, 29]], SC: [[290, 299]], SD: [[570, 577]], TN: [[370, 385]],
  TX: [[733, 733], [750, 799], [885, 885]], UT: [[840, 847]], VT: [[50, 59]], VA: [[201, 201], [220, 246]],
  WA: [[980, 994]], WV: [[247, 268]], WI: [[530, 549]], WY: [[820, 831]],
};

const defaultState = {
  profile: {
    stateCode: "CA",
    zipcode: "",
    county: "",
    disasterType: "",
    housingDamage: "not sure",
    insuranceStatus: "not sure",
    householdSize: 1,
    situation: "",
    safeNow: null,
    medicalNeed: false,
    mobilityNeed: false,
    shelterNeed: false,
    foodNeed: false,
    documentsNeed: false,
    petNeed: false,
    incomeDisrupted: false,
  },
  messages: [],
  history: [],
  latestEvidence: null,
};

const resourceCache = { federal: null, states: {} };
const elements = {
  chatLog: document.querySelector("#chatLog"),
  chatInput: document.querySelector("#chatInput"),
  sendChatButton: document.querySelector("#sendChatButton"),
  backendMode: document.querySelector("#backendMode"),
  evidencePanel: document.querySelector("#evidencePanel"),
};

let appState = structuredClone(defaultState);

function cannedOpener() {
  return `
    <h3>Let’s start with the basics</h3>
    <p>Tell me what happened and where you are. I’ll infer your state and build a recovery profile from your chat.</p>
    <p>Helpful details:</p>
    <ul>
      <li>ZIP code or state</li>
      <li>Wildfire or earthquake or other</li>
      <li>Whether you are safe right now</li>
      <li>Housing damage</li>
      <li>Shelter, food, medical, insurance, documents, or pet needs</li>
      <li>How many people are in your household</li>
    </ul>
  `;
}

function inferStateFromZip(zipcode) {
  const digits = String(zipcode || "").replace(/\D/g, "").slice(0, 5);
  if (digits.length !== 5) return null;
  const zip3 = Number(digits.slice(0, 3));
  for (const [stateCode, ranges] of Object.entries(ZIP3_STATE_RANGES)) {
    for (const [start, end] of ranges) {
      if (zip3 >= start && zip3 <= end) return stateCode;
    }
  }
  return null;
}

function inferStateFromText(text) {
  const zip = text.match(/\b\d{5}\b/)?.[0];
  const fromZip = inferStateFromZip(zip || "");
  if (fromZip) return fromZip;
  const lower = text.toLowerCase();
  for (const [code, name] of Object.entries(STATE_NAMES)) {
    if (lower.includes(name.toLowerCase())) return code;
  }
  const abbrev = text.match(/\b([A-Z]{2})\b/)?.[1];
  if (abbrev && STATE_NAMES[abbrev]) return abbrev;
  return null;
}

function normalizeResource(record, jurisdiction, fallbackStateCode) {
  return {
    name: record.name,
    category: record.category,
    jurisdiction,
    url: record.url,
    description: record.description,
    stateCode: record.state_code || fallbackStateCode,
    disasterTypes: record.disaster_types || ["wildfire", "earthquake"],
    tags: record.tags || [],
    requiredInformation: record.required_information || [],
    requiredDocuments: record.required_documents || [],
  };
}

async function loadFederalResources() {
  if (resourceCache.federal) return resourceCache.federal;
  const response = await fetch(FEDERAL_DB_PATH);
  if (!response.ok) throw new Error("Could not load local federal resources.");
  resourceCache.federal = (await response.json()).map((record) => normalizeResource(record, "federal", "US"));
  return resourceCache.federal;
}

async function loadStateResources(stateCode) {
  const code = (stateCode || "CA").toUpperCase();
  if (resourceCache.states[code]) return resourceCache.states[code];
  const response = await fetch(STATE_DB_PATH(code));
  if (!response.ok) throw new Error(`Could not load local ${code} resources.`);
  resourceCache.states[code] = (await response.json()).map((record) => normalizeResource(record, "state", code));
  return resourceCache.states[code];
}

function parseProfileFromPrompt(prompt, currentProfile) {
  const next = { ...currentProfile };
  const zipMatch = prompt.match(/\b\d{5}\b/);
  if (zipMatch) {
    next.zipcode = zipMatch[0];
    next.stateCode = inferStateFromZip(zipMatch[0]) || next.stateCode;
  }

  const stateCode = inferStateFromText(prompt);
  if (stateCode) next.stateCode = stateCode;

  const countyMatch = prompt.match(/([A-Z][a-z]+(?:\s[A-Z][a-z]+)*) County/i);
  if (countyMatch) next.county = countyMatch[0];

  if (/\b(wildfire|fire|smoke|evacuat)/i.test(prompt)) next.disasterType = "wildfire";
  if (/\b(earthquake|quake|aftershock)/i.test(prompt)) next.disasterType = "earthquake";

  if (/\b(destroyed|total loss)\b/i.test(prompt)) next.housingDamage = "destroyed";
  else if (/\b(major damage|severe damage|badly damaged)\b/i.test(prompt)) next.housingDamage = "major damage";
  else if (/\b(minor damage)\b/i.test(prompt)) next.housingDamage = "minor damage";

  if (/\bunderinsured\b/i.test(prompt)) next.insuranceStatus = "underinsured";
  else if (/\buninsured\b/i.test(prompt)) next.insuranceStatus = "uninsured";
  else if (/\binsured\b/i.test(prompt)) next.insuranceStatus = "insured";

  const householdMatch = prompt.match(/\b(\d+)\s+(people|person|adults|children|kids|family|household)\b/i);
  if (householdMatch) next.householdSize = Number(householdMatch[1]);

  if (/\b(not safe|unsafe|danger|rescue)\b/i.test(prompt)) next.safeNow = false;
  if (/\b(safe now|staying with|at a hotel|at a shelter|with family|with friends)\b/i.test(prompt)) next.safeNow = true;

  if (/\b(shelter|nowhere to stay|hotel voucher|evacuated)\b/i.test(prompt)) next.shelterNeed = true;
  if (/\b(food|groceries|hungry)\b/i.test(prompt)) next.foodNeed = true;
  if (/\b(document|documents|id|passport|birth certificate)\b/i.test(prompt)) next.documentsNeed = true;
  if (/\b(pet|dog|cat|animal)\b/i.test(prompt)) next.petNeed = true;
  if (/\b(medical|medication|oxygen|injured)\b/i.test(prompt)) next.medicalNeed = true;
  if (/\b(wheelchair|mobility|accessible|disability)\b/i.test(prompt)) next.mobilityNeed = true;
  if (/\b(income|job|unemployed|missed work)\b/i.test(prompt)) next.incomeDisrupted = true;

  next.situation = prompt.trim();
  return next;
}

async function selectResources(profile) {
  const [federalResources, stateResources] = await Promise.all([
    loadFederalResources(),
    loadStateResources(profile.stateCode || "CA"),
  ]);
  const resources = [...federalResources, ...stateResources];
  const selected = [];

  for (const resource of resources) {
    if (profile.disasterType && !resource.disasterTypes.includes(profile.disasterType)) continue;
    let include = false;
    if (["state emergency coordination", "federal aid", "insurance support", "local referrals", "food and benefits", "preparedness and recovery"].includes(resource.category)) include = true;
    if (profile.shelterNeed && resource.tags.includes("shelter")) include = true;
    if (profile.foodNeed && resource.tags.includes("food")) include = true;
    if (profile.petNeed && resource.tags.includes("pets")) include = true;
    if (profile.insuranceStatus !== "insured" && resource.tags.includes("insurance")) include = true;
    if (profile.incomeDisrupted && resource.tags.includes("benefits")) include = true;
    if (profile.disasterType === "wildfire" && resource.tags.includes("fire")) include = true;
    if (profile.disasterType === "earthquake" && resource.tags.includes("earthquake")) include = true;
    if (include) selected.push(resource);
  }
  return selected.slice(0, 10);
}

async function buildPlan(profile) {
  const stateName = STATE_NAMES[profile.stateCode] || profile.stateCode || "Selected State";
  const immediate = [];
  const next = [];
  const warnings = [];
  const docs = [
    "government ID if available",
    "household member names and birth dates",
    "current phone number and safe contact information",
  ];

  if (profile.safeNow === false) immediate.push("You are not currently safe. Move to a safer location and call 911 if there is immediate danger.");

  if (profile.disasterType === "wildfire") {
    immediate.push("Monitor evacuation orders and fire updates before returning to any affected area.");
    immediate.push("Avoid smoke exposure when possible, especially for children, older adults, and anyone with breathing issues.");
    warnings.push("Do not re-enter an evacuation zone until local officials say it is safe.");
  } else if (profile.disasterType === "earthquake") {
    immediate.push("Watch for aftershocks and avoid structures with visible structural damage.");
    immediate.push("Shut off utilities only if you suspect leaks or damage and know it is safe to do so.");
    warnings.push("Aftershocks can happen after the initial quake; damaged buildings may become more dangerous over time.");
  }

  if (profile.medicalNeed) immediate.push("Prioritize medication access, medical devices, and transportation to care if needed.");
  if (profile.shelterNeed) next.push(profile.stateCode === "CA" ? "Find same-day shelter options through 211 California or the Red Cross." : "Find same-day shelter options through your state emergency management agency, local 211 if available, or the Red Cross.");
  if (profile.foodNeed) next.push(profile.stateCode === "CA" ? "Locate food distribution or emergency food support through 211 California and CalFresh partners." : "Locate food distribution or emergency food support through your state emergency management agency, local 211 if available, or state benefit agencies.");
  if (["major damage", "destroyed"].includes(profile.housingDamage)) {
    next.push("Document all property damage with photos and notes before cleanup if it is safe to do so.");
    next.push("Start insurance and disaster assistance applications as soon as possible.");
    docs.push("photos or videos of damage", "lease, mortgage, or proof of address", "insurance policy number and insurer contact details");
  }
  if (["underinsured", "uninsured", "not sure"].includes(profile.insuranceStatus)) next.push("Check for state and federal disaster assistance, and ask for insurance counseling if coverage is unclear.");
  if (profile.documentsNeed) {
    next.push("Make a list of missing IDs, insurance papers, banking records, and school or medical documents for replacement.");
    docs.push("a list of missing documents and any backups you still have");
  }
  if (profile.incomeDisrupted) next.push("Review emergency food, unemployment, and local cash-assistance pathways if work has been interrupted.");
  if (profile.mobilityNeed) warnings.push("Ask for accessible shelter, transportation, and medical-device support early, since these resources can fill quickly.");
  if (profile.petNeed) next.push("Ask shelters and county services about pet-friendly sheltering or animal evacuation support.");

  const resources = await selectResources(profile);
  return {
    title: `${stateName} ${profile.disasterType ? capitalize(profile.disasterType) : "Disaster"} Recovery Plan`,
    stateName,
    riskLevel: profile.safeNow === false || profile.medicalNeed || profile.shelterNeed ? "high" : "moderate",
    immediatePriorities: dedupe(immediate),
    next24Hours: dedupe(next),
    documentsToGather: dedupe(docs),
    warnings: dedupe(warnings),
    resources,
    stateResources: resources.filter((resource) => resource.jurisdiction === "state"),
    federalResources: resources.filter((resource) => resource.jurisdiction === "federal"),
  };
}

function dedupe(items) {
  return [...new Set(items)];
}

function capitalize(value) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
}

function profileSummary(profile) {
  const parts = [];
  if (profile.zipcode) parts.push(`ZIP ${profile.zipcode}`);
  if (profile.stateCode) parts.push(STATE_NAMES[profile.stateCode] || profile.stateCode);
  if (profile.county) parts.push(profile.county);
  if (profile.disasterType) parts.push(profile.disasterType);
  parts.push(`${profile.householdSize} in household`);
  if (profile.shelterNeed) parts.push("needs shelter");
  if (profile.foodNeed) parts.push("needs food");
  if (profile.documentsNeed) parts.push("missing documents");
  if (profile.insuranceStatus !== "not sure") parts.push(profile.insuranceStatus);
  return parts.join(" | ");
}

function renderSection(title, items) {
  if (!items.length) return "";
  return `<h3>${title}</h3><ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderResourceLines(resources) {
  if (!resources.length) return "<p>No strong matches yet from the local database.</p>";
  return `<ul>${resources.map((resource) => `<li><strong>${escapeHtml(resource.name)}</strong>: ${escapeHtml(resource.description)} <a href="${resource.url}" target="_blank" rel="noreferrer">Open</a></li>`).join("")}</ul>`;
}

function renderDocumentsByService(resources) {
  if (!resources.length) return "";
  return `
    <h3>Information and documents by service</h3>
    <ul>
      ${resources.map((resource) => {
        const info = resource.requiredInformation.length ? resource.requiredInformation.join(", ") : "none listed";
        const docs = resource.requiredDocuments.length ? resource.requiredDocuments.join(", ") : "none listed";
        return `<li><strong>${escapeHtml(resource.name)}</strong><br />Information needed: ${escapeHtml(info)}<br />Documents to prepare: ${escapeHtml(docs)}</li>`;
      }).join("")}
    </ul>
  `;
}

function renderFullPlan(plan, profile) {
  return `
    <h3>${escapeHtml(plan.title)}</h3>
    <p><strong>Risk level:</strong> ${escapeHtml(plan.riskLevel)}</p>
    <p><strong>Inferred profile:</strong> ${escapeHtml(profileSummary(profile))}</p>
    ${renderSection("Immediate priorities", plan.immediatePriorities)}
    ${renderSection("Next 24 hours", plan.next24Hours)}
    <h3>State and local services</h3>
    ${renderResourceLines(plan.stateResources)}
    <h3>Federal services</h3>
    ${renderResourceLines(plan.federalResources)}
    ${renderDocumentsByService(plan.resources)}
    ${renderSection("Documents to gather", plan.documentsToGather)}
    ${renderSection("Warnings", plan.warnings)}
  `;
}

function isLikelyQuestion(prompt) {
  const lower = prompt.toLowerCase().trim();
  return lower.includes("?") || /^(what|which|how|where|can|do|am|should|who)\b/.test(lower);
}

function targetedReply(plan, profile, prompt) {
  const lower = prompt.toLowerCase();
  if (lower.includes("document")) {
    return `
      <h3>Documents to gather first</h3>
      ${renderSection("Priority documents", plan.documentsToGather)}
      ${renderDocumentsByService(plan.resources)}
    `;
  }
  if (lower.includes("federal")) {
    return `<h3>Federal services that may be relevant</h3>${renderResourceLines(plan.federalResources)}`;
  }
  if (lower.includes("state") || lower.includes("local")) {
    return `<h3>State and local services that may be relevant</h3>${renderResourceLines(plan.stateResources)}`;
  }
  if (lower.includes("qualif")) {
    return `
      <h3>Qualification check</h3>
      <p>I can suggest resources that may be relevant, but I cannot confirm that you qualify from chat alone.</p>
      <p>Based on your profile, these are the strongest matches to check officially:</p>
      ${renderResourceLines(plan.resources.slice(0, 5))}
    `;
  }
  if (lower.includes("first") || lower.includes("immediate")) {
    return `<h3>What to do first</h3>${renderSection("Immediate priorities", plan.immediatePriorities)}${renderSection("Next 24 hours", plan.next24Hours)}`;
  }
  return `
    <h3>Updated local guidance</h3>
    <p>I updated your profile for ${escapeHtml(STATE_NAMES[profile.stateCode] || profile.stateCode)} and pulled the strongest matches from the local databases.</p>
    ${renderSection("Next 24 hours", plan.next24Hours)}
  `;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderInlineMarkdown(text) {
  let rendered = escapeHtml(text);
  rendered = rendered.replace(/`([^`]+)`/g, "<code>$1</code>");
  rendered = rendered.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  rendered = rendered.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  rendered = rendered.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  rendered = rendered.replace(/_([^_]+)_/g, "<em>$1</em>");
  rendered = rendered.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  return rendered;
}

function renderMarkdown(markdown) {
  const normalized = String(markdown || "").replace(/\r\n/g, "\n").trim();
  if (!normalized) return "<p></p>";

  const codeBlocks = [];
  let working = normalized.replace(/```([\w-]*)\n?([\s\S]*?)```/g, (_match, language, code) => {
    const html = `<pre><code class="code-block${language ? ` language-${escapeHtml(language)}` : ""}">${escapeHtml(code.trim())}</code></pre>`;
    codeBlocks.push(html);
    return `@@CODEBLOCK_${codeBlocks.length - 1}@@`;
  });

  const lines = working.split("\n");
  const html = [];
  let paragraph = [];
  let listItems = [];

  const isTableRow = (value) => /\|/.test(value);
  const isTableDivider = (value) => /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(value);
  const splitTableRow = (value) => value
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());

  const flushParagraph = () => {
    if (!paragraph.length) return;
    html.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
    paragraph = [];
  };

  const flushList = () => {
    if (!listItems.length) return;
    html.push(`<ul>${listItems.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</ul>`);
    listItems = [];
  };

  for (let index = 0; index < lines.length; index += 1) {
    const rawLine = lines[index];
    const line = rawLine.trim();

    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }

    const codeBlockMatch = line.match(/^@@CODEBLOCK_(\d+)@@$/);
    if (codeBlockMatch) {
      flushParagraph();
      flushList();
      html.push(codeBlocks[Number(codeBlockMatch[1])]);
      continue;
    }

    if (isTableRow(line) && lines.length > 1) {
      const nextLine = lines[index + 1]?.trim() || "";
      if (isTableDivider(nextLine)) {
        flushParagraph();
        flushList();

        const headerCells = splitTableRow(line);
        const bodyRows = [];
        let tableIndex = index + 2;

        while (tableIndex < lines.length) {
          const candidate = lines[tableIndex].trim();
          if (!candidate || !isTableRow(candidate) || isTableDivider(candidate)) break;
          bodyRows.push(splitTableRow(candidate));
          tableIndex += 1;
        }

        const thead = `<thead><tr>${headerCells.map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`).join("")}</tr></thead>`;
        const tbody = bodyRows.length
          ? `<tbody>${bodyRows.map((row) => `<tr>${row.map((cell) => `<td>${renderInlineMarkdown(cell)}</td>`).join("")}</tr>`).join("")}</tbody>`
          : "";
        html.push(`<table>${thead}${tbody}</table>`);
        index = tableIndex - 1;
        continue;
      }
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = Math.min(headingMatch[1].length, 6);
      html.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      continue;
    }

    const blockquoteMatch = line.match(/^>\s?(.*)$/);
    if (blockquoteMatch) {
      flushParagraph();
      flushList();
      html.push(`<blockquote>${renderInlineMarkdown(blockquoteMatch[1])}</blockquote>`);
      continue;
    }

    const listMatch = line.match(/^[-*]\s+(.*)$/);
    if (listMatch) {
      flushParagraph();
      listItems.push(listMatch[1]);
      continue;
    }

    flushList();
    paragraph.push(line);
  }

  flushParagraph();
  flushList();

  return html.join("");
}

function appendMessage(role, html) {
  appState.messages.push({ role, html, createdAt: new Date().toISOString() });
  renderMessages();
}

function appendHistory(role, text) {
  appState.history.push({ role, text, createdAt: new Date().toISOString() });
  appState.history = appState.history.slice(-12);
}

function renderMessages() {
  if (!appState.messages.length) {
    appState.messages = [{ role: "assistant", html: cannedOpener() }];
  }
  elements.chatLog.innerHTML = appState.messages.map((message) => `
    <article class="chat-message ${message.role}">
      <div class="chat-role">${escapeHtml(message.role)}</div>
      <div class="chat-body">${message.html}</div>
    </article>
  `).join("");
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
}

function renderEvidencePanel(toolResult) {
  if (!elements.evidencePanel) return;
  if (!toolResult || !toolResult.results || !toolResult.results.length) {
    elements.evidencePanel.innerHTML = `
      <section class="evidence-empty">
        <p class="evidence-kicker">Waiting for evidence</p>
        <p>Ask a question in chat to see the grounded resources, source modes, and likely document requirements used for the latest answer.</p>
      </section>
    `;
    return;
  }

  const resourceCards = toolResult.results.map((item) => {
    const infoList = item.required_information?.length
      ? `<ul>${item.required_information.map((entry) => `<li>${escapeHtml(entry)}</li>`).join("")}</ul>`
      : "<p>None listed.</p>";
    const docsList = item.required_documents?.length
      ? `<ul>${item.required_documents.map((entry) => `<li>${escapeHtml(entry)}</li>`).join("")}</ul>`
      : "<p>None listed.</p>";
    return `
      <article class="evidence-item">
        <p class="evidence-kicker">${escapeHtml(item.jurisdiction)} resource</p>
        <h3>${escapeHtml(item.name)}</h3>
        <p class="evidence-meta">
          Source mode: <strong>${escapeHtml(item.source_mode)}</strong>
          ${item.score ? ` | Match score: <strong>${escapeHtml(item.score)}</strong>` : ""}
        </p>
        <p>${escapeHtml(item.snippet || "No summary available.")}</p>
        <div class="evidence-tags">
          <span class="evidence-tag">${escapeHtml(item.state_code || "US")}</span>
          <span class="evidence-tag">${escapeHtml(item.source_mode)}</span>
        </div>
        <p><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">Open source</a></p>
        <h3>Required information</h3>
        ${infoList}
        <h3>Required documents</h3>
        ${docsList}
      </article>
    `;
  }).join("");

  elements.evidencePanel.innerHTML = `
    <section class="evidence-group">
      <p class="evidence-kicker">Latest lookup</p>
      <h3>${escapeHtml(toolResult.query || "Current grounded query")}</h3>
      <p class="evidence-meta">State scope: <strong>${escapeHtml(toolResult.state_code || "Unknown")}</strong></p>
    </section>
    <section class="evidence-list">
      ${resourceCards}
    </section>
  `;
}

async function callBackend(prompt, profile, plan, backendMode = "auto") {
  const normalizedMode = ["auto", "online", "local"].includes(backendMode) ? backendMode : "auto";
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt,
      profile,
      plan,
      history: appState.history,
      backend_mode: normalizedMode,
      prefer_local: normalizedMode === "local",
    }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.details || payload.error || `Backend request failed with status ${response.status}`);
  }

  return response.json();
}

async function respondToPrompt(prompt) {
  appState.profile = parseProfileFromPrompt(prompt, appState.profile);
  appendHistory("user", prompt);
  appendMessage("user", `<p>${escapeHtml(prompt)}</p>`);
  const plan = await buildPlan(appState.profile);
  const backendMode = elements.backendMode?.value || "auto";

  try {
    const backend = await callBackend(prompt, appState.profile, plan, backendMode);
    appState.latestEvidence = backend.tool_result || null;
    renderEvidencePanel(appState.latestEvidence);
    appendHistory("assistant", backend.answer);
    appendMessage(
      "assistant",
      `<h3>Nemotron response</h3>${renderMarkdown(backend.answer)}<p><strong>Backend:</strong> ${escapeHtml(backend.backend)}</p>`,
    );
    return;
  } catch (error) {
    appState.latestEvidence = {
      query: prompt,
      state_code: appState.profile.stateCode,
      results: plan.resources.slice(0, 5).map((resource) => ({
        name: resource.name,
        jurisdiction: resource.jurisdiction,
        state_code: resource.stateCode,
        source_mode: "local-plan",
        score: 0,
        snippet: resource.description,
        url: resource.url,
        required_information: resource.requiredInformation,
        required_documents: resource.requiredDocuments,
      })),
    };
    renderEvidencePanel(appState.latestEvidence);
    appendMessage("system", `<p>Model backend failed in <strong>${escapeHtml(backendMode)}</strong> mode. Details: ${escapeHtml(error.message)}</p>`);
  }
}

elements.sendChatButton.addEventListener("click", async () => {
  const prompt = elements.chatInput.value.trim();
  if (!prompt) return;
  elements.chatInput.value = "";
  await respondToPrompt(prompt);
});

elements.chatInput.addEventListener("keydown", async (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    const prompt = elements.chatInput.value.trim();
    if (!prompt) return;
    elements.chatInput.value = "";
    await respondToPrompt(prompt);
  }
});

renderMessages();
renderEvidencePanel(appState.latestEvidence);
