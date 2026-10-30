# CV Generator

App local para adaptar el CV de cualquier usuario una vacante, encolar generaciones (Gemini) y descargar PDF/DOCX. No es un wrapper de un prompt: el modelo **no inventa empresas, fechas ni métricas**; reescribe sobre un perfil maestro.

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

- Una clave de [Google AI Studio](https://aistudio.google.com/apikey) (Gemini), o de [OpenAI](https://platform.openai.com/api-keys)
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

**Por la pantalla Skills.** Con front y back corriendo, abre http://localhost:3000/skills. **Guardar cambios** (o Ctrl+S / ⌘S) escribe `master_profile.json`. El siguiente CV ya usa esos hechos. No hace falta reiniciar.

Desde ahí se edita:

- nombre, títulos profesionales, resumen y contacto
- experiencia: empresa, roles, fechas, responsabilidades, tecnologías y logros. Se pueden agregar, reordenar y quitar empleos
- proyectos, educación, certificaciones e idiomas
- skills por categoría (lenguajes, frontend, backend, mobile, bases de datos, cloud, DevOps, testing, arquitectura, pagos, security, AI, soft skills)

Si el perfil del repo no es el tuyo, cambia esos datos antes de generar. Si no, los CVs siguen saliendo con la trayectoria de ejemplo.

El mismo archivo se puede editar a mano. La pantalla es el camino normal.

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
     cola (lote de 5) ──► Gemini u OpenAI
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

`knowledge_base/cv_1.json`, `cv_2.json` y `cv_3.json` se eliminaron en `ebc18f7`: eran copias viejas del perfil (p. ej. UffPay «Ene 2023 – Jul 2024») y el tailor ya no las usaba para hechos. El *matcher* (`matcher.py`) sigue leyendo `cv_*.json` si alguien agrega plantillas; sin ellas usa una base derivada del maestro (`compact_master.base_cv_from_master`, id `master_profile`) que solo trae identidad y contacto. El perfil compacto que ve el modelo se calcula en cada generación (`GET /v1/master-profile/compact` para revisarlo); ya no se exporta a disco. En `sources[]` del maestro, `src_kb_cv1..3` quedan como evidencia histórica (`status: removed`, recuperables con `git show ebc18f7~1:<ruta>`).

#### Verificación antes de entregar un CV

`_build_cv` (en `llm/cv_builder.py`, compartido por Gemini y OpenAI) devuelve el CV y un reporte. Las notas salen en `notes_to_verify` (respuesta del API e historial) y en `raw_meta.verification`.

- **Fechas en conflicto.** Un empleo con `dateConflict.status: "unresolved"` (hoy UffPay y Monkey Cave) sale sin periodo y sus fechas no se mandan al modelo. Las `dates` que escriba el modelo nunca se usan. Se resuelve con `PUT /v1/master-profile/validations` (`experience.UffPay.startDate` / `experience.MonkeyCave.dates`, valor `AAAA-MM – AAAA-MM` o `AAAA-MM – Actualidad`) o cambiando la fecha en el editor; guardar el perfil con las mismas fechas no cuenta como resolución.
- **Hechos sin respaldo.** Se descarta un bullet con una cifra que no está en ese empleo, una cifra junto a un proyecto que `metrics[]` no asigna a ese proyecto (el 35% es de Grainchain, no de Safra Bank) o una tecnología que solo está en la vacante. Las tecnologías de la vacante pueden ir en skills/keywords, no en la experiencia. Si faltan bullets se rellena con hechos del maestro, nunca con frases genéricas.
- **Proyectos incompletos.** Sin tecnologías ni funcionalidades confirmadas (Altos Aceros, Safra Bank) o `status: incomplete` no van al prompt; siguen en el maestro. Las notas internas de las descripciones («sin confirmar») se quitan y los `UNRESOLVED:` de `evidence` se pasan como `unknown[]`.
- **Idioma.** `language_guard.py` detecta `en` / `es` / `mixed` / `unknown` por texto (palabras funcionales, verbos, títulos y morfología; empresas, proyectos y tecnologías no votan). Lo que está en el otro idioma o mezclado se manda a traducir al mismo proveedor; la traducción se acepta solo si queda en el idioma pedido y conserva números, fechas y nombres protegidos. Hay un reintento; si falla, se conserva el texto original y se reporta. Nunca se borra contenido ni se cambia por un texto genérico. `unknown` (p. ej. «Angular, NgRx») se deja igual. Es una heurística: limitaciones en el docstring del módulo.
- **Ubicación.** `profile.contact.location` guarda el dato («Mexico»), pero no se imprime: `cvGenerationRules.omitContactFields` (y la resolución del conflicto de ubicación como «omitido en CVs 2025–2026») lo excluyen del CV.

### Regenerar CVs del historial

En **Historial**, «Regenerar este CV» (detalle) o marca varios y pulsa «Regenerar N». Usa la vacante guardada y el pipeline actual, así se prueban cambios sin buscar la vacante otra vez. Cada regeneración es una entrada nueva («<nombre> (regenerado)», con enlace al original); el original no se toca. Sale en lotes de 5 por petición y un lote parcial no espera a juntar 5. API: `POST /v1/history/regenerate` con `{"ids": [...]}` (máx. 30).

Los cargos de cada empleo se eligen entre los cargos validados del perfil según la familia del puesto al que te postulas (React Native/móvil, Frontend, Full Stack, Backend). Si un empleo no tiene un cargo de esa familia, se deja el real y sale una nota en «Para revisar».

### Tests del backend

```bash
backend/.venv/bin/pip install pytest
cd backend && .venv/bin/python -m pytest -q
```

No llaman a ningún modelo: `tests/fakes.py` sustituye la llamada HTTP por respuestas fijas (incluida la traducción) y los E2E corren el pipeline completo contra `knowledge_base/master_profile.json`.

### Flujo de un CV

1. `POST /v1/queue` (extensión o “Añadir al lote”) o `POST /v1/optimize` (espera el resultado).
2. `cv_queue.py` — jobs en `optimize_queue.json`. Al juntar **5**, una llamada `tailor_cv_batch`. “Generar lote” hace flush de 1–4.
3. `vacancy_pipeline.py` — limpia texto, elige plantilla (base del maestro si no hay `cv_*.json`), llama al LLM, `append_generated_cv`.
4. `llm/gemini_backend.py` u `llm/openai_backend.py`. Prompts en `llm/prompts.py`.
5. `_build_cv` en `llm/cv_builder.py` (compartido; `result_to_cv` devuelve solo el CV) — empresas solo las del maestro; fechas del maestro (omitidas si están en conflicto); verificación de hechos; paso de idioma con traducción validada; `%` en vez de `percent`; skills del maestro + overlay de la vacante (C#/.NET si el modelo los pide); stack en `skill_stack.py`.

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

`career_kb.py` + `PUT /v1/master-profile`. La pestaña Skills (`/skills`) escribe identidad, contacto, experiencia, proyectos, educación, certificaciones, idiomas y skills en `master_profile.json`. El siguiente CV ya usa lo guardado.

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
