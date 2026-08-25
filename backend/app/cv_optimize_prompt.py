"""Misma intención que `lib/cv-optimize-prompt.ts` en el front (optimización ATS)."""

OPTIMIZE_ATS_INSTRUCTIONS = """
MODO: OPTIMIZACIÓN ATS Y ALINEACIÓN CON LA VACANTE (prioridad máxima sobre redacción genérica).

Objetivo: maximizar coincidencia con el texto de la oferta usando técnicas habituales en mercado y parsers ATS:
- title (titular del CV bajo el nombre): adáptalo al título del puesto de la vacante con la misma formulación que el anuncio cuando sea razonable (orden de palabras, mayúsculas, «Frontend Senior» vs «Senior Frontend», etc.), sin inventar un seniority superior al que respalda la experiencia; si el anuncio da varias variantes, usa la del título principal o la más repetida.
- Replica la nomenclatura canónica de tus skills; si la oferta usa un alias (ej. «NEXT» vs «Next.js»), deja el canónico y el alias entre paréntesis: «Next.js (NEXT)».
- Unifica sinónimos hacia el término de la vacante: si pide «metodologías ágiles» y solo mencionas «Scrum», usa formulaciones del estilo «Metodologías ágiles (Scrum)» o equivalente con el wording del anuncio.
- Extrae keywords, herramientas, dominios y responsabilidades del enunciado e interprétalos sobre tu experiencia real: reformula bullets y el resumen para reflejar esos términos sin inventar cargos, fechas ni empresas.
- tech_skills y stack: alinea categorías y redacción con el léxico de la vacante; agrupa o renombra etiquetas solo cuando sea honesto (misma competencia, distinto nombre).
- Mantén hechos verificables; si amplías redacción o infieres una competencia razonable desde lo ya descrito, márcalo con [VALIDAR] en bullets o notas según las reglas del sistema.
""".strip()
