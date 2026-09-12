/**
 * Extrae el texto útil de una vacante (título, empresa, ubicación, descripción)
 * y descarta navegación, botones, insights de match y listados.
 */
(function (root) {
  "use strict";

  const EXPAND_RE =
    /ver m[aá]s|see more|show more|mostrar m[aá]s|see full|mostrar todo|read more|leer m[aá]s/i;

  const JOB_POST_SUFFIX_RE = /\s*[-–—]\s*job post\s*$/i;

  function firstText(root, selectors) {
    if (!root) return "";
    for (const sel of selectors) {
      const el = root.querySelector(sel);
      if (!el) continue;
      const t = cleanLine(el.innerText || el.textContent || "");
      if (t) return t;
    }
    return "";
  }

  function cleanLine(s) {
    return String(s || "")
      .replace(JOB_POST_SUFFIX_RE, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function normalizeBlock(s) {
    return String(s || "")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n[ \t]+/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function uniqueLines(lines) {
    const seen = new Set();
    const out = [];
    for (const line of lines) {
      const t = cleanLine(line);
      if (!t) continue;
      const key = t.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(t);
    }
    return out;
  }

  function elementToText(el) {
    if (!el) return "";
    const clone = el.cloneNode(true);
    clone
      .querySelectorAll(
        "script,style,noscript,svg,button,nav,footer,form,iframe,[aria-hidden='true']"
      )
      .forEach((n) => n.remove());
    clone.querySelectorAll("br").forEach((br) => br.replaceWith("\n"));
    clone.querySelectorAll("li").forEach((li) => {
      const t = (li.textContent || "").trim();
      if (!t) return;
      if (!/^\s*[-•]/.test(t)) li.prepend(document.createTextNode("- "));
    });
    return normalizeBlock(clone.innerText || clone.textContent || "");
  }

  function linkedinAboutJob(doc) {
    return (
      (doc && doc.querySelector('[id^="JobDetails_AboutTheJob_"]')) ||
      null
    );
  }

  function descriptionRoot(doc) {
    const documentRef = doc || document;
    return (
      linkedinAboutJob(documentRef) ||
      documentRef.querySelector("#jobsearch-ViewjobPaneWrapper") ||
      documentRef.querySelector(".jobsearch-JobComponent") ||
      documentRef.querySelector(".jobs-description") ||
      documentRef.querySelector(".jobs-details") ||
      documentRef.querySelector("#job-details") ||
      documentRef.querySelector("#job-body") ||
      documentRef.querySelector("#job-detail-container") ||
      documentRef.querySelector("[data-offers-grid-detail-container]") ||
      documentRef.querySelector(".gb-landing-cover") ||
      documentRef.querySelector("main:not(#workspace)") ||
      documentRef
    );
  }

  function clickExpanders(scope) {
    const root = scope || descriptionRoot(document);
    root.querySelectorAll("button, a[role='button']").forEach((el) => {
      const label = `${el.innerText || ""} ${el.getAttribute("aria-label") || ""}`;
      if (!EXPAND_RE.test(label)) return;
      if (el.getAttribute("aria-expanded") === "true") return;
      try {
        el.click();
      } catch {
        /* ignore */
      }
    });
  }

  function siteFromHost(host) {
    const h = String(host || "")
      .replace(/^www\./, "")
      .toLowerCase();
    if (h === "indeed.com" || h.endsWith(".indeed.com")) return "indeed";
    if (h === "linkedin.com" || h.endsWith(".linkedin.com")) return "linkedin";
    if (h === "glassdoor.com" || h.endsWith(".glassdoor.com")) return "glassdoor";
    if (h.includes("computrabajo.")) return "computrabajo";
    if (h === "occ.com.mx" || h.endsWith(".occ.com.mx")) return "occ";
    if (
      h === "getonbrd.com" ||
      h.endsWith(".getonbrd.com") ||
      h === "getonboard.com" ||
      h.endsWith(".getonboard.com")
    ) {
      return "getonboard";
    }
    return "generic";
  }

  const DROP_HEADING =
    /^(beneficios|benefits|perks|prestaciones|what we offer|lo que (te )?ofrecemos|ofrecemos|about (the )?(company|us|our team)|acerca de (la |nuestra )?empresa|sobre (la empresa|nosotros|la compa[nñ][ií]a)|qui[eé]nes somos|our (culture|values)|nuestra cultura|equal opportunity|diversity|inclusi[oó]n)\b/i;

  const KEEP_HEADING =
    /^(descripci[oó]n|puesto|requirements?|requisitos|responsabilidades|responsibilities|qualifications|skills|habilidades|experiencia|stack|tecnolog|funciones|obligaciones|about the (role|job|position)|the role|el (puesto|rol)|what you.?ll do|qu[eé] (har[aá]s|buscamos))\b/i;

  function stripVacancyFiller(text) {
    if (!text) return "";
    const out = [];
    let dropping = false;
    for (const raw of String(text).split("\n")) {
      const heading = raw.trim().replace(/[:.\s]+$/, "");
      if (DROP_HEADING.test(heading)) {
        dropping = true;
        continue;
      }
      if (dropping && KEEP_HEADING.test(heading)) dropping = false;
      if (!dropping) out.push(raw);
    }
    return normalizeBlock(out.join("\n"));
  }

  function queryParam(href, names) {
    try {
      const u = new URL(href, "https://example.com");
      for (const name of names) {
        const value = u.searchParams.get(name);
        if (value) return value;
      }
    } catch {
      /* ignore */
    }
    return "";
  }

  function httpOrigin(loc) {
    const origin = (loc && loc.origin) || "";
    if (/^https?:\/\//i.test(origin)) return origin.replace(/\/$/, "");
    const host = (loc && loc.hostname) || "";
    if (host) return `https://${host}`;
    return "";
  }

  function canonicalJobUrl(site, loc, doc) {
    const href = (loc && loc.href) || "";
    const origin = httpOrigin(loc);
    if (site === "indeed") {
      let jk = queryParam(href, ["jk", "vjk"]);
      const win = doc.defaultView;
      if (!jk && win && win._initialData) {
        const init = win._initialData;
        jk =
          init.autoOpenTwoPaneJobKey ||
          (init.autoOpenJobAttributes && init.autoOpenJobAttributes.jobKey) ||
          "";
      }
      if (!jk) {
        const pane =
          doc.querySelector("#jobsearch-ViewjobPaneWrapper") || doc;
        const a = pane.querySelector('a[href*="jk="], a[href*="vjk="]');
        if (a) jk = queryParam(a.getAttribute("href") || "", ["jk", "vjk"]);
      }
      if (!jk) {
        const m = href.match(/[?&](?:jk|vjk)=([a-z0-9]+)/i);
        if (m) jk = m[1];
      }
      if (jk && origin) return `${origin}/viewjob?jk=${encodeURIComponent(jk)}`;
      if (/\/viewjob/i.test((loc && loc.pathname) || "") && /^https?:/i.test(href)) {
        return href.split("#")[0];
      }
      return /^https?:/i.test(href) ? href.split("#")[0] : "";
    }
    if (site === "linkedin") {
      const id = linkedinJobId(loc, doc);
      if (id) return `https://www.linkedin.com/jobs/view/${id}`;
      return "";
    }
    if (site === "occ") {
      const id = occJobId(loc, doc);
      if (id) return `https://www.occ.com.mx/empleo/oferta/${id}`;
      return "";
    }
    if (site === "getonboard") {
      const canonical = doc.querySelector('link[rel="canonical"]');
      const canonHref = canonical && canonical.getAttribute("href");
      if (canonHref && /^https?:/i.test(canonHref)) return canonHref.split("#")[0];
      const og = doc.querySelector('meta[property="og:url"]');
      const ogHref = og && og.getAttribute("content");
      if (ogHref && /^https?:/i.test(ogHref)) return ogHref.split("#")[0];
      const path = (loc && loc.pathname) || "";
      const m = path.match(/\/empleos\/[^/]+\/([^/?#]+)/);
      if (m && origin) return `${origin}${path.split("?")[0]}`;
      return href.split("?")[0] || href.split("#")[0] || "";
    }
    return href.split("#")[0] || "";
  }

  function extractIndeed(doc) {
    const pane =
      doc.querySelector("#jobsearch-ViewjobPaneWrapper") ||
      doc.querySelector(".jobsearch-JobComponent") ||
      doc.querySelector(".jobsearch-ViewJobLayout--embedded") ||
      doc;

    const title = firstText(pane, [
      '[data-testid="jobsearch-JobInfoHeader-title"]',
      ".jobsearch-JobInfoHeader-title",
      "h1.jobsearch-JobInfoHeader-title",
      "h1",
    ]);
    const company = firstText(pane, [
      '[data-testid="inlineHeader-companyName"]',
      '[data-company-name="true"]',
      '[data-testid="inlineHeader-companyName"] a',
    ]);
    const location = firstText(pane, [
      '[data-testid="inlineHeader-companyLocation"]',
      '[data-testid="job-location"]',
    ]);

    const other = pane.querySelector(
      '[data-testid="jobsearch-OtherJobDetailsContainer"]'
    );
    const salaryBox = pane.querySelector("#salaryInfoAndJobType");
    const extra = uniqueLines(
      ((other || salaryBox)?.innerText || "").split("\n")
    ).filter(
      (line) =>
        line !== "-" &&
        line.length > 1 &&
        !/\$|sueldo|salary|por mes|al mes|per month|a year/i.test(line)
    );

    const descEl =
      pane.querySelector("#jobDescriptionText") ||
      pane.querySelector(".jobsearch-JobComponent-description") ||
      doc.querySelector("#jobDescriptionText");
    const description = elementToText(descEl);

    return { title, company, location, extra, description };
  }

  function linkedinJobId(loc, doc) {
    const href = (loc && loc.href) || "";
    const path = (loc && loc.pathname) || "";
    const fromPath = path.match(/\/jobs\/view\/(\d+)/);
    if (fromPath) return fromPath[1];
    const fromQuery = queryParam(href, ["currentJobId"]);
    if (fromQuery && /^\d{5,}$/.test(fromQuery)) return fromQuery;
    const about = linkedinAboutJob(doc);
    if (about) {
      const fromAbout = String(about.id || "").match(/(\d{5,})$/);
      if (fromAbout) return fromAbout[1];
    }
    const slot = doc && doc.querySelector('[id^="JobDetails_"]');
    if (slot) {
      const fromSlot = String(slot.id || "").match(/(\d{5,})$/);
      if (fromSlot) return fromSlot[1];
    }
    const link = doc && doc.querySelector('a[href*="/jobs/view/"]');
    if (link) {
      const fromLink = (link.getAttribute("href") || "").match(/\/jobs\/view\/(\d+)/);
      if (fromLink) return fromLink[1];
    }
    return "";
  }

  function linkedinTitleCompany(doc) {
    const raw = String((doc && doc.title) || "")
      .replace(/\s*\|\s*LinkedIn\s*$/i, "")
      .trim();
    const parts = raw.split("|").map((p) => cleanLine(p)).filter(Boolean);
    return { title: parts[0] || "", company: parts[1] || "" };
  }

  function stripLinkedinSearchChrome(text) {
    const raw = String(text || "");
    if (!raw) return "";
    const low = raw.toLowerCase();
    const looksLikeSearchList =
      /\d+\s+resultados/.test(low) ||
      /c[oó]mo se clasifican los anuncios/.test(low) ||
      (low.match(/adel[aá]ntate a solicitar/g) || []).length >= 2;
    if (looksLikeSearchList) {
      const markers = [
        "acerca del empleo",
        "about the job",
        "about this job",
        "job description",
        "descripci\u00f3n del empleo",
      ];
      let cut = -1;
      for (const marker of markers) {
        const i = low.indexOf(marker);
        if (i >= 0 && (cut < 0 || i < cut)) cut = i;
      }
      if (cut >= 0) return normalizeBlock(raw.slice(cut));
    }
    return normalizeBlock(
      raw
        .split("\n")
        .filter((line) => {
          const t = line.trim();
          if (!t) return true;
          return !/^\d+\s+resultados\b|^c[oó]mo se clasifican|^adel[aá]ntate a solicitar|^solicitud sencilla|^publicado hace|^visto ·|^¿estos resultados|^abonarse a premium|^mira empleos donde figuras|^reactivar premium|^linkedin corporation/i.test(
            t,
          );
        })
        .join("\n"),
    );
  }

  function extractLinkedin(doc) {
    const about = linkedinAboutJob(doc);
    const pane =
      about ||
      doc.querySelector(".jobs-details") ||
      doc.querySelector(".jobs-search__job-details") ||
      doc.querySelector(".job-view-layout") ||
      null;

    const fromTitle = linkedinTitleCompany(doc);
    const title =
      firstText(pane, [
        ".job-details-jobs-unified-top-card__job-title h1",
        ".job-details-jobs-unified-top-card__job-title",
        "h1.t-24",
        "h1",
      ]) || fromTitle.title;
    const companyEl = doc.querySelector(
      '[aria-label^="Empresa,"], [aria-label^="Company,"]',
    );
    const companyAria = cleanLine(
      (companyEl && companyEl.getAttribute("aria-label")) || "",
    );
    const company =
      firstText(pane || doc, [
        ".job-details-jobs-unified-top-card__company-name a",
        ".job-details-jobs-unified-top-card__company-name",
        ".jobs-unified-top-card__company-name",
      ]) ||
      (companyAria && companyAria.replace(/^(empresa|company)\s*,\s*/i, "")) ||
      fromTitle.company;
    const location = firstText(pane, [
      ".job-details-jobs-unified-top-card__primary-description-container",
      ".jobs-unified-top-card__bullet",
      ".jobs-unified-top-card__tertiary-description-container",
    ]);

    const descEl =
      about ||
      (pane &&
        (pane.querySelector("#job-details") ||
          pane.querySelector(".jobs-description__content") ||
          pane.querySelector(".jobs-box__html-content") ||
          pane.querySelector(".jobs-description-content__text") ||
          pane.querySelector(".jobs-description")));
    const description = stripLinkedinSearchChrome(elementToText(descEl));

    return { title, company, location, extra: [], description };
  }

  function extractGlassdoor(doc) {
    const title = firstText(doc, [
      '[data-test="job-title"]',
      ".JobDetails_jobTitle",
      "h1",
    ]);
    const company = firstText(doc, [
      '[data-test="employer-name"]',
      ".JobDetails_companyName",
    ]);
    const location = firstText(doc, ['[data-test="location"]']);
    const descEl =
      doc.querySelector('[data-test="jobDescriptionText"]') ||
      doc.querySelector(".JobDetails_jobDescription") ||
      doc.querySelector("#JobDescriptionContainer");
    return {
      title,
      company,
      location,
      extra: [],
      description: elementToText(descEl),
    };
  }

  function extractComputrabajo(doc) {
    const title = firstText(doc, ["h1.titulo", "h1"]);
    const company = firstText(doc, [".dFlex .fc_base", ".box_offer h1 + p"]);
    const descEl =
      doc.querySelector("#jobDescription") ||
      doc.querySelector(".box_desc") ||
      doc.querySelector("div.fs16");
    return {
      title,
      company,
      location: firstText(doc, [".fs16.fc_aux", ".box_offer .mbB"]),
      extra: [],
      description: elementToText(descEl),
    };
  }

  function extractGetOnBoard(doc) {
    const title = firstText(doc, [
      'h1.gb-landing-cover__title [itemprop="title"]',
      "h1.gb-landing-cover__title",
      '[itemprop="title"]',
      "h1",
    ]);
    const company = firstText(doc, [
      '[itemprop="hiringOrganization"] [itemprop="name"]',
      '.gb-landing-cover a[href*="/companies/"] strong',
      "strong[itemprop='name']",
    ]);
    const location = firstText(doc, [
      '[itemprop="jobLocation"] .location',
      '[itemprop="jobLocation"]',
      ".gb-landing-cover .location",
    ]);
    const seniority = firstText(doc, ['[itemprop="qualifications"]']);
    const modality = firstText(doc, [
      ".gb-landing-cover h2.size1",
    ]);
    const extra = uniqueLines([
      seniority,
      /full[-\s]?time/i.test(modality) ? "Full time" : "",
      /part[-\s]?time/i.test(modality) ? "Part time" : "",
      ...Array.from(
        doc.querySelectorAll('.gb-tags[itemprop="skills"] .gb-tags__item'),
      ).map((el) => cleanLine(el.innerText || el.textContent || "")),
    ]).filter(
      (line) =>
        line &&
        line !== title &&
        line !== company &&
        !/^(programaci[oó]n|m[aá]s trabajos)/i.test(line),
    );

    const descRoot = doc.querySelector("#job-body") ||
      doc.querySelector('[itemprop="description"]');
    let description = elementToText(descRoot);
    description = description
      .replace(/Postula a este empleo a través de Get on Board\.?/gi, "")
      .replace(/GETONBRD Job ID:\s*\d+/gi, "")
      .replace(/\n{3,}/g, "\n\n")
      .trim();

    return { title, company, location, extra, description };
  }

  function occJobId(loc, doc) {
    const href = (loc && loc.href) || "";
    const fromQ = queryParam(href, ["jobid"]);
    if (fromQ && /^\d+$/.test(fromQ)) return fromQ;
    const path = (loc && loc.pathname) || "";
    const fromPath = path.match(/\/empleo\/oferta\/(\d+)/i);
    if (fromPath) return fromPath[1];
    const share = doc.querySelector(
      "[data-url*='/empleo/oferta/'], [data-url-offer-copy*='/empleo/oferta/']",
    );
    if (share) {
      const raw =
        share.getAttribute("data-url") ||
        share.getAttribute("data-url-offer-copy") ||
        "";
      const m = raw.match(/\/empleo\/oferta\/(\d+)/i);
      if (m) return m[1];
    }
    const marked = doc.querySelector(
      "#job-detail-container [data-id], [data-offers-grid-detail-container][data-id]",
    );
    const dataId = marked && marked.getAttribute("data-id");
    if (dataId && /^\d+$/.test(dataId)) return dataId;
    const idLine = Array.from(doc.querySelectorAll("p")).find((p) =>
      /^ID:\s*\d+/i.test(cleanLine(p.innerText || p.textContent || "")),
    );
    if (idLine) {
      const m = cleanLine(idLine.innerText || "").match(/ID:\s*(\d+)/i);
      if (m) return m[1];
    }
    return "";
  }

  function occDetailRoot(doc) {
    const desktop =
      doc.querySelector("#job-detail-container [data-offer-content]") ||
      doc.querySelector("#job-detail-container [data-offers-grid-detail-container]") ||
      doc.querySelector("#job-detail-container");
    if (desktop && occHasJobBody(desktop)) return desktop;
    const mobile = doc.querySelector(
      '[data-offers-grid-detail-container="mobile"]',
    );
    if (mobile && occHasJobBody(mobile)) return mobile;
    const standalone =
      doc.querySelector("article .rich-text") ||
      doc.querySelector("main .rich-text") ||
      doc.querySelector(".rich-text");
    if (standalone) {
      return standalone.closest("article") || standalone.closest("main") || standalone;
    }
    return desktop || mobile;
  }

  function occHasJobBody(root) {
    if (!root) return false;
    if (root.querySelector("[data-offers-grid-detail-title], .rich-text")) {
      return true;
    }
    return elementToText(root).length > 120;
  }

  function stripOccChrome(text) {
    if (!text) return "";
    const drop =
      /^(postularme|compartir( en (facebook|x))?|copiar enlace|empresa verificada|reportar vacante|vacantes similares|enviar correo|datos de contacto|recuerda que ning[uú]n reclutador|id:\s*\d+)\b/i;
    const kept = String(text)
      .split("\n")
      .filter((line) => !drop.test(cleanLine(line)));
    return normalizeBlock(kept.join("\n"));
  }

  function extractOcc(doc) {
    const root = occDetailRoot(doc) || doc;
    const title = firstText(root, [
      "[data-offers-grid-detail-title]",
      "p.font-h4-m",
      "h1",
    ]);
    const company = firstText(root, [
      'a[href*="/empleos/bolsa-de-trabajo-"]',
    ]).replace(/^empresa verificada$/i, "");
    const location = firstText(root, [
      ".icon-location-pin + label",
      ".line-clamp-1 label",
    ]);
    const moneyEl = root.querySelector(".i_money");
    const salary = moneyEl
      ? cleanLine((moneyEl.closest("p") || moneyEl.parentElement || moneyEl).innerText || "")
      : "";
    const extra = uniqueLines([
      salary,
      ...Array.from(root.querySelectorAll(".icon-journey + p, .icon-journey ~ p"))
        .map((el) => cleanLine(el.innerText || el.textContent || ""))
        .filter(Boolean),
    ]).filter(
      (line) =>
        line &&
        line !== title &&
        line !== company &&
        !/empresa verificada/i.test(line),
    );
    const descEl =
      root.querySelector(".rich-text") ||
      root.querySelector(".break-words.mb-8") ||
      root;
    return {
      title,
      company,
      location,
      extra,
      description: stripOccChrome(elementToText(descEl)),
    };
  }

  function extractGeneric(doc) {
    const jsonLd = jobPostingFromLd(doc);
    if (jsonLd && (jsonLd.description || "").length > 80) return jsonLd;

    const title = firstText(doc, ["h1"]);
    const selectors = [
      "[itemprop='description']",
      "#job-description",
      "#jobDescription",
      ".job-description",
      ".jobDescription",
      "[class*='jobDescription']",
      "[class*='job-description']",
      "article",
      "main",
      "[role='main']",
    ];
    let description = "";
    for (const sel of selectors) {
      const el = doc.querySelector(sel);
      const t = elementToText(el);
      if (t.length > description.length) description = t;
    }
    if (description.length > 18_000) {
      description = "";
    }
    return { title, company: "", location: "", extra: [], description };
  }

  function jobPostingFromLd(doc) {
    const scripts = doc.querySelectorAll('script[type="application/ld+json"]');
    for (const s of scripts) {
      let data;
      try {
        data = JSON.parse(s.textContent || "");
      } catch {
        continue;
      }
      const items = Array.isArray(data) ? data : [data];
      const stack = [...items];
      while (stack.length) {
        const item = stack.pop();
        if (!item || typeof item !== "object") continue;
        if (Array.isArray(item["@graph"])) stack.push(...item["@graph"]);
        const type = item["@type"];
        const isJob =
          type === "JobPosting" ||
          (Array.isArray(type) && type.includes("JobPosting"));
        if (!isJob) continue;
        const tmp = doc.createElement("div");
        tmp.innerHTML = item.description || "";
        const org = item.hiringOrganization;
        const company =
          typeof org === "string" ? org : org && org.name ? org.name : "";
        const loc = item.jobLocation;
        let location = "";
        if (typeof loc === "string") location = loc;
        else if (loc && loc.address) {
          const a = loc.address;
          location = [a.addressLocality, a.addressRegion, a.addressCountry]
            .filter(Boolean)
            .join(", ");
        }
        return {
          title: item.title || "",
          company,
          location,
          extra: item.employmentType ? [String(item.employmentType)] : [],
          description: elementToText(tmp),
        };
      }
    }
    return null;
  }

  function compose({ title, company, location, extra, description, url }) {
    const lines = [];
    if (title) lines.push(title);
    if (company) lines.push(`Empresa: ${company}`);
    if (url) lines.push(`URL: ${url}`);
    const rest = uniqueLines([location, ...(extra || [])]);
    if (rest.length) lines.push(rest.join("\n"));
    const parts = [];
    if (lines.length) parts.push(lines.join("\n"));
    const cleaned = stripVacancyFiller(description || "");
    if (cleaned) parts.push(cleaned);
    return normalizeBlock(parts.join("\n\n"));
  }

  function extractRecord(doc, loc) {
    const documentRef = doc || document;
    const locationRef =
      loc || (typeof location !== "undefined" ? location : { hostname: "", href: "" });
    const site = siteFromHost(locationRef.hostname);
    let rec = null;
    if (site === "indeed") rec = extractIndeed(documentRef);
    else if (site === "linkedin") rec = extractLinkedin(documentRef);
    else if (site === "glassdoor") rec = extractGlassdoor(documentRef);
    else if (site === "computrabajo") rec = extractComputrabajo(documentRef);
    else if (site === "occ") rec = extractOcc(documentRef);
    else if (site === "getonboard") rec = extractGetOnBoard(documentRef);
    else rec = extractGeneric(documentRef);

    if (site === "linkedin" && rec && !(rec.description || "").length) {
      const fromLd = jobPostingFromLd(documentRef);
      if (fromLd && (fromLd.description || "").length > 80) {
        rec = {
          title: rec.title || fromLd.title,
          company: rec.company || fromLd.company,
          location: rec.location || fromLd.location,
          extra: fromLd.extra || [],
          description: stripLinkedinSearchChrome(fromLd.description),
        };
      }
    } else if (
      site !== "linkedin" &&
      site !== "occ" &&
      (!rec || !(rec.description || "").length)
    ) {
      rec = extractGeneric(documentRef) || rec || {
        title: "",
        company: "",
        location: "",
        extra: [],
        description: "",
      };
    }
    rec.url = canonicalJobUrl(site, locationRef, documentRef);
    return rec;
  }

  function extractVacancy(doc, loc) {
    return compose(extractRecord(doc, loc)).slice(0, 40_000);
  }

  root.__cvGen = {
    extractVacancy,
    extractRecord,
    elementToText,
    clickExpanders,
    descriptionRoot,
    siteFromHost,
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
