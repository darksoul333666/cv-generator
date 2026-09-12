# CV Generator

App local para adaptar el CV de Jairo a una vacante, encolar generaciones (Gemini) y descargar PDF/DOCX. No es un wrapper de un prompt: el modelo **no inventa empresas, fechas ni métricas**; reescribe sobre un perfil maestro.

Puertos fijos:

| Pieza | URL |
|---|---|
| Frontend (Next.js) | http://localhost:3000 |
| Backend (FastAPI) | http://127.0.0.1:8000 |
| Extensión Chrome | se inyecta en Indeed, LinkedIn, OCC, Computrabajo, Get on Board, Glassdoor |

El **historial de CVs** no está en el navegador ni en el puerto 3000. Vive en disco y lo sirve el backend en `:8000`:

- `backend/.cache/generated_cvs.json` — CVs listos (máx. 100)
- `backend/.cache/optimize_queue.json` — cola (queued / generating / error)

Si mueves el front a otro puerto (p. ej. 3002), dejas de ver la UI que ya tenías en `:3000` (localStorage del objetivo diario). El historial sigue en `.cache` mientras el API esté en **8000**.

Arranque:

```bash
./run-all.sh
```

Requiere `backend/.venv` con `backend/requirements.txt` y `backend/.env` (`GEMINI_API_KEY`, `GEMINI_MODEL`).

---

## Vista general

```
Vacante (web o extensión)
        │
        ▼
   Next.js :3000          Chrome MV3
   (pegar / historial /       │
    skills / PDF-DOCX)        │ POST /v1/queue
        │                     │
        └────────┬────────────┘
                 ▼
          FastAPI :8000
                 │
     parse vacante (Empresa/URL se quedan
     en historial; no van al LLM)
                 │
     cola (lote de 5) ──► Gemini o Ollama
                 │
     perfil maestro + plantilla keyword
                 │
     CV JSON ──► .cache/generated_cvs.json
                 │
          front descarga PDF (Puppeteer)
          o DOCX en el cliente
```

---

## Frontend (`app/`, `components/`, `lib/`)

Next.js (App Router) en el puerto **3000**. Habla con FastAPI por `NEXT_PUBLIC_PY_API_URL` o `http://127.0.0.1:8000` (`lib/api.ts`).

Páginas:

- `/` — pegar vacante, encolar, ver resultado
- `/historial` — lista + filtros; lee `GET /v1/history`
- `/skills` — conflictos y skills del maestro

Piezas útiles:

- `lib/vacancy-meta.ts` — saca `Empresa:` y `URL:` del texto (OCC/LinkedIn canónicos)
- `lib/cv-template-html.ts` + `app/api/pdf/route.ts` — HTML → PDF Letter (márgenes en Puppeteer)
- `lib/cv-docx.ts` — DOCX en el browser
- `lib/daily-goal.ts` — objetivo 40/día; el *conteo* sale del historial del backend (`ready` de hoy); el *on/off* está en `localStorage` de **localhost:3000**

El front no guarda CVs. Si el historial “desaparece”, casi siempre es que el API no está en `:8000` o se borró `.cache`.

---

## Extensión (`chrome-extension/`)

MV3, versión en `manifest.json`. Carga desempaquetada desde esa carpeta.

- `extract.js` — texto de la vacante por sitio (LinkedIn panel, OCC `#job-detail-container`, Indeed, etc.) y URL canónica
- `content.js` — botones Copiar / Generar CV; solo se muestran si `jobPanePresent()` (en OCC: `/empleos/` o `?jobid=`)
- `background.js` — `POST http://127.0.0.1:8000/v1/queue`, abre historial en `http://localhost:3000`, alarmas del objetivo

Tras cambiar código: recargar en `chrome://extensions`.

---

## Backend (`backend/app/`) — el núcleo

FastAPI (`uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`). CORS abierto a localhost.

### Datos que no se mandan al LLM

`vacancy_clean.parse_pasted_vacancy`:

- Cuerpo de la oferta → modelo
- `Empresa` y `URL` → solo historial
- Quita beneficios / about de empresa
- Normaliza LinkedIn (`/jobs/view/{id}`) y OCC (`/empleo/oferta/{id}`)

### Perfil maestro

Fuente de verdad: `backend/knowledge_base/master_profile.json`.

`compact_master.py` arma el JSON corto que ve el modelo (experiencias, métricas, inventario de skills). Educación y certificaciones **no las reescribe el LLM**: salen fijas (`locale_util`).

Plantillas en `knowledge_base/cv_*.json` solo sirven al *matcher* por keywords (`matcher.py`). El tailor usa el maestro.

### Flujo de un CV

1. `POST /v1/queue` (extensión o “Añadir al lote”) o `POST /v1/optimize` (espera el resultado).
2. `cv_queue.py` — jobs en `optimize_queue.json`. Al juntar **5**, una llamada `tailor_cv_batch`. “Generar lote” hace flush de 1–4.
3. `vacancy_pipeline.py` — limpia texto, elige plantilla, llama al LLM, `append_generated_cv`.
4. `llm/gemini_backend.py` (prod) u `ollama_backend.py`. Prompts en `llm/prompts.py`.
5. `_ollama_result_to_cv` (compartido) — empresas solo las del maestro; fechas del maestro; `%` en vez de `percent`; skills del maestro + overlay de la vacante (C#/.NET si el modelo los pide); stack en `skill_stack.py`.

No reintentar 429 de Gemini (cuota diaria).

### Historial (la “memoria”)

`cv_history.py`:

| Campo | Uso |
|---|---|
| `id` | UUID |
| `vacancy_title` / `vacancy_text` | oferta |
| `company_name` / `vacancy_url` | metadatos, no van al modelo |
| `cv` | JSON del CV adaptado |
| `match_percent` | autoevaluación del modelo |
| `created_at` | objetivo diario cuenta solo `ready` de hoy |

API: `GET /v1/history`, `GET /v1/history/{id}`, `PATCH` para renombrar.

Copia de seguridad: duplica `backend/.cache/generated_cvs.json`.

### Skills / validaciones

`career_kb.py` + `PUT /v1/master-profile/skills|validations|experience`. La pestaña Skills escribe el maestro; el siguiente CV ya usa esos hechos.

### Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/health` | vivo |
| POST | `/v1/queue` | encola |
| GET | `/v1/queue/status` | cola |
| POST | `/v1/queue/flush` | genera 1–4 ya |
| POST | `/v1/optimize` | encola y espera |
| GET | `/v1/history` | lista |
| GET/PATCH | `/v1/history/{id}` | detalle / nombre |
| POST | `/v1/match` | solo plantilla, sin LLM |
| GET/PUT | `/v1/master-profile…` | maestro |
| GET | `/v1/cvs` | plantillas |

Rutas extra de la extensión: `extension_routes.py`.

---

## Cómo explicarlo en 60 segundos

El front es una UI. La extensión solo extrae y encola. El backend guarda historial en JSON, mete 5 vacantes en un lote, y Gemini reescribe bullets/summary/title sobre un perfil cerrado. PDF y DOCX se arman después, en el cliente o en `/api/pdf`.

---

## Si el historial “no está”

1. `curl -s http://127.0.0.1:8000/health` — el API tiene que ser **8000**.
2. Que exista `backend/.cache/generated_cvs.json` (no lo subas a git si pesa; es local).
3. Abre el front en **http://localhost:3000**, no en 3002.
4. Recarga la extensión: el historial se abre en `:3000`.
