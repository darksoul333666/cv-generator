# CV Generator

App local para adaptar el CV de Jairo a una vacante, encolar generaciones (Gemini) y descargar PDF/DOCX. No es un wrapper de un prompt: el modelo **no inventa empresas, fechas ni métricas**; reescribe sobre un perfil maestro.

El repo trae un perfil de ejemplo. **Antes de generar un CV hay que reemplazarlo por el tuyo** (nombre, empresas, fechas, métricas y skills). El modelo no inventa esos hechos: reescribe solo lo que está en `backend/knowledge_base/master_profile.json`.

---

## Cómo levantarlo

### Requisitos

- [Node.js](https://nodejs.org/) 20 o superior (`node -v`)
- [npm](https://docs.npmjs.com/) (viene con Node)
- **Python 3.11 o 3.12**. Python 3.9 también instala las dependencias. **Python 3.14 no**: `pydantic` no compila ahí. En macOS, `python3` de Homebrew puede ser 3.14; usa el del sistema o uno instalado aparte:

```bash
python3 --version
# si sale 3.14, prueba:
/usr/bin/python3 --version
```

- Una clave de [Google AI Studio](https://aistudio.google.com/apikey) (Gemini), de [OpenAI](https://platform.openai.com/api-keys), o [Ollama](https://ollama.com/) corriendo en local
- Chrome, solo si vas a usar la extensión

### 1. Clonar e instalar el frontend

```bash
git clone <url-del-repo>
cd cv-generator
npm install
```

### 2. Entorno de Python del backend

El script `./run-all.sh` espera el intérprete en `backend/.venv`. Créalo con un Python 3.9–3.13:

```bash
# macOS con el Python del sistema (3.9), si Homebrew es 3.14:
/usr/bin/python3 -m venv backend/.venv

# o, si tienes 3.11 / 3.12:
# python3.12 -m venv backend/.venv

backend/.venv/bin/pip install --upgrade pip
backend/.venv/bin/pip install -r backend/requirements.txt
```

Comprueba que Gemini se importa:

```bash
backend/.venv/bin/python -c "from google import genai; print('ok')"
```

### 3. Variables de entorno

El backend **solo** lee `backend/.env` (no el `.env` de la raíz).

```bash
cp backend/.env.example backend/.env
```

Edita `backend/.env` y deja un solo proveedor activo:

| `LLM_PROVIDER` | Qué hace falta |
|---|---|
| `gemini` (default) | `GEMINI_API_KEY` y `GEMINI_MODEL` |
| `openai` | `OPENAI_API_KEY` y `OPENAI_MODEL` |
| `ollama` | Ollama en `OLLAMA_HOST` (default `http://127.0.0.1:11434`) y el modelo `OLLAMA_MODEL` |

Ejemplo mínimo con Gemini:

```bash
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-3.6-flash
GEMINI_API_KEY=tu_clave
```

No subas `backend/.env` a git. Ya está en `backend/.gitignore`.

El frontend habla con el API en `http://127.0.0.1:8000`. Solo hace falta un `.env` en la raíz si quieres cambiar eso con `NEXT_PUBLIC_PY_API_URL`.

### 4. Arrancar

```bash
./run-all.sh
```

Eso levanta las dos piezas y las detiene juntas con Ctrl+C:

| Pieza | URL |
|---|---|
| Frontend (Next.js) | http://localhost:3000 |
| Backend (FastAPI) | http://127.0.0.1:8000 |
| Docs del API | http://127.0.0.1:8000/docs |

Comprueba que el backend responde:

```bash
curl -s http://127.0.0.1:8000/health
```

Si el puerto 3000 ya está ocupado, Next usa otro (3001, 3002…). El historial y la extensión asumen **localhost:3000**. Libera el 3000 y vuelve a correr `./run-all.sh`.

Para arrancarlos por separado:

```bash
# terminal 1
cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# terminal 2, en la raíz
npm run dev
```

### 5. Perfilar el CV a tu expertise

`backend/knowledge_base/master_profile.json` es la fuente de verdad. El archivo que viene en el repo es un perfil de ejemplo (nombre, contacto, empresas, métricas y skills de otra persona). Si no lo cambias, cada CV generado seguirá hablando de esa trayectoria.

Hay dos formas de dejarlo en tu expertise. Las dos escriben el mismo JSON.

**Por la pantalla Skills (lo habitual para skills y fechas).** Con front y back corriendo, abre http://localhost:3000/skills.

Ahí puedes:

- agregar o quitar skills por categoría (lenguajes, frontend, backend, mobile, bases de datos, cloud, DevOps, testing, arquitectura, pagos, security, AI, soft skills)
- reordenar experiencias y ajustar fechas, si es el empleo actual, y el tipo (fijo, freelance, contrato, remoto, presencial)
- resolver conflictos cuando el JSON tiene dos valores para el mismo dato (email, teléfono, etc.)

**Guardar cambios** (o Ctrl+S / ⌘S) hace `PUT` al backend y actualiza `master_profile.json`. El siguiente CV ya usa esos hechos. No hace falta reiniciar.

La pantalla **no** crea empresas ni reescribe el resumen, los títulos ni la educación. Esos campos se editan en el JSON.

**Editando el JSON (obligatorio si el perfil no es el tuyo).** Abre `backend/knowledge_base/master_profile.json` y sustituye al menos:

| Campo | Para qué |
|---|---|
| `profile.fullName` | nombre que sale en el CV |
| `profile.professionalTitles` | títulos entre los que el modelo elige según la vacante |
| `profile.contact` | email, teléfono, LinkedIn, ubicación |
| `profile.summary` | resumen base; el modelo lo reescribe, no lo inventa de cero |
| `experience[]` | empresas, roles, fechas y logros. **Solo aparecen empresas que estén aquí** |
| `skills` | inventario que la pantalla Skills también edita |
| educación y certificaciones | salen fijas en el CV; el modelo no las reescribe |

Reglas que el generador respeta:

- no inventa empresas, fechas ni métricas que no estén en el maestro
- educación y certificaciones se copian tal cual
- skills del CV salen del maestro, reordenadas según la vacante
- después de guardar (en Skills o en el archivo), genera un CV de prueba en http://localhost:3000 y revisa que el nombre y las empresas sean los tuyos

Si el JSON queda inválido, `/skills` muestra los errores de validación y no conviene generar hasta corregirlos.

### 6. Extensión de Chrome (opcional)

1. Abre `chrome://extensions`
2. Activa **Modo de desarrollador**
3. **Cargar descomprimida** y elige la carpeta `chrome-extension/`
4. Tras cambiar su código, pulsa recargar en esa misma página

Inyecta botones en Indeed, LinkedIn, OCC, Computrabajo, Get on Board y Glassdoor. Encola contra `http://127.0.0.1:8000` y abre el historial en `http://localhost:3000`. El backend tiene que estar arriba.

---

## Puertos e historial

| Pieza | URL |
|---|---|
| Frontend (Next.js) | http://localhost:3000 |
| Backend (FastAPI) | http://127.0.0.1:8000 |
| Extensión Chrome | se inyecta en Indeed, LinkedIn, OCC, Computrabajo, Get on Board, Glassdoor |

El **historial de CVs** no está en el navegador ni en el puerto 3000. Vive en disco y lo sirve el backend en `:8000`:

- `backend/.cache/generated_cvs.json` — CVs listos (máx. 100)
- `backend/.cache/optimize_queue.json` — cola (queued / generating / error)

Si mueves el front a otro puerto (p. ej. 3002), dejas de ver la UI que ya tenías en `:3000` (localStorage del objetivo diario). El historial sigue en `.cache` mientras el API esté en **8000**.

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

Fuente de verdad: `backend/knowledge_base/master_profile.json`. Cómo reemplazar el perfil de ejemplo por el tuyo está en [Perfilar el CV a tu expertise](#5-perfilar-el-cv-a-tu-expertise).

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

`career_kb.py` + `PUT /v1/master-profile/skills|validations|experience`. La pestaña Skills (`/skills`) escribe skills, fechas de experiencia y conflictos en `master_profile.json`. Nombre, contacto, empresas, logros y educación se editan en ese JSON. El siguiente CV ya usa lo guardado.

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
