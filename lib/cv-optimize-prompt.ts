/**
 * Instrucciones inyectadas en /v1/tailor junto con la vacante para la pestaña «Optimizar CV».
 * El backend las añade al contexto; refuerzan match léxico/semántico tipo ATS sin sustituir la vacante.
 */
export const CV_OPTIMIZE_ATS_INSTRUCTIONS = `
MODO: OPTIMIZACIÓN ATS Y ALINEACIÓN CON LA VACANTE (prioridad máxima sobre redacción genérica).

Objetivo: maximizar coincidencia con el texto de la oferta usando técnicas habituales en mercado y parsers ATS:
- Replica la nomenclatura EXACTA de la vacante cuando describas una competencia que ya posees (ej.: si la oferta dice «NEXT» y en el CV figura «Next.js», escribe «NEXT» o la variante literal que use la oferta en skills/stack/bullets donde aplique).
- Unifica sinónimos hacia el término de la oferta: si pide «metodologías ágiles» y solo mencionas «Scrum», usa formulaciones del estilo «Metodologías ágiles (Scrum)» o equivalente con el wording del anuncio.
- Extrae keywords, herramientas, dominios y responsabilidades del enunciado e interprétalos sobre tu experiencia real: reformula bullets y el resumen para reflejar esos términos sin inventar cargos, fechas ni empresas.
- tech_skills y stack: alinea categorías y redacción con el léxico de la vacante; agrupa o renombra etiquetas solo cuando sea honesto (misma competencia, distinto nombre).
- Mantén hechos verificables; si amplías redacción o infieres una competencia razonable desde lo ya descrito, márcalo con [VALIDAR] en bullets o notas según las reglas del sistema.
`.trim();
