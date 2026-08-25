import { z } from "zod";
import { MASTER_SKILL_KINDS, type MasterProfile } from "./master-profile";

export const evidenceLevelSchema = z.enum([
  "verified",
  "documented",
  "claimed",
  "mentioned",
  "inferred",
  "conflicted",
]);

export const conflictImpactSchema = z.enum([
  "critical",
  "high",
  "medium",
  "low",
]);

const isoYearOrMonth = z
  .string()
  .regex(/^\d{4}(-\d{2})?$/, "Fecha debe ser YYYY o YYYY-MM")
  .or(z.literal(""));

const optionalDate = z.union([isoYearOrMonth, z.null()]).optional();

const contactCandidateSchema = z.object({
  value: z.string().min(1),
  evidenceLevel: evidenceLevelSchema,
  sourceRefs: z.array(z.string()),
  userValidated: z.boolean(),
});

const contactFieldSchema = z.object({
  value: z.string().nullable(),
  status: z.string().min(1),
  evidenceLevel: evidenceLevelSchema.optional(),
  sourceCount: z.number().int().nonnegative().nullable().optional(),
  userValidated: z.boolean(),
  candidates: z.array(contactCandidateSchema),
});

const masterSkillsSchema = z.object({
  languages: z.array(z.string()),
  frontend: z.array(z.string()),
  backend: z.array(z.string()),
  mobile: z.array(z.string()),
  databases: z.array(z.string()),
  cloud: z.array(z.string()),
  devops: z.array(z.string()),
  testing: z.array(z.string()),
  architecture: z.array(z.string()),
  payments: z.array(z.string()),
  security: z.array(z.string()),
  ai: z.array(z.string()),
  softSkills: z.array(z.string()),
});

const skillSchema = z.object({
  id: z.string().min(1),
  canonical: z.string().min(1),
  aliases: z.array(z.string()),
  categories: z.array(z.string()),
  evidenceLevel: evidenceLevelSchema,
  sourceCount: z.number().nullable().optional(),
  userValidated: z.boolean(),
});

const achievementSchema = z.object({
  description: z.string(),
  metric: z.object({
    value: z.number().nullable(),
    unit: z.string(),
    type: z.string(),
  }),
  status: z.string(),
  evidenceLevel: evidenceLevelSchema.optional(),
  safeForCV: z.boolean().optional(),
  requiresUserValidation: z.boolean().optional(),
});

const experienceSchema = z.object({
  id: z.string().min(1),
  company: z.string().min(1),
  roles: z.array(z.string()).min(1),
  employmentType: z.string().nullable(),
  startDate: z.union([isoYearOrMonth, z.null()]),
  endDate: z.union([isoYearOrMonth, z.null()]),
  current: z.boolean().optional(),
  sortOrder: z.number().int().nonnegative().optional(),
  dateStatus: z.string(),
  sourceValues: z.record(z.string(), z.unknown()),
  originalValues: z.record(z.string(), z.unknown()).optional(),
  userValidated: z.boolean(),
  conflicts: z.array(z.string()),
  domain: z.array(z.string()),
  responsibilities: z.array(z.string()),
  technologies: z.array(z.string()),
  achievements: z.array(achievementSchema),
  evidence: z.array(z.string()),
  sourceRefs: z.array(z.string()),
  evidenceLevel: evidenceLevelSchema,
  sourceCount: z.number().int().nonnegative(),
});

const projectSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  type: z.string(),
  description: z.string(),
  domain: z.array(z.string()),
  platforms: z.array(z.string()),
  features: z.array(z.string()),
  technologies: z.array(z.string()),
  scale: z.string().nullable(),
  status: z.string(),
  evidenceLevel: evidenceLevelSchema,
  sourceCount: z.number().int().nonnegative(),
  userValidated: z.boolean(),
  evidence: z.array(z.string()),
  sourceRefs: z.array(z.string()),
  isEmployment: z.boolean(),
  relevantForRoles: z.array(z.string()).optional(),
  relevantWhenVacancyNeeds: z.array(z.string()).optional(),
});

const metricSchema = z.object({
  id: z.string().min(1),
  value: z.number().nullable(),
  unit: z.string().min(1),
  type: z.string().min(1),
  description: z.string(),
  company: z.string(),
  project: z.string(),
  status: z.string(),
  confidence: z.string(),
  evidenceLevel: evidenceLevelSchema,
  sourceCount: z.number().int().nonnegative(),
  userValidated: z.boolean(),
  safeForCV: z.boolean(),
  requiresUserValidation: z.boolean(),
  experienceId: z.string().nullable().optional(),
  projectId: z.string().nullable().optional(),
  sourceRefs: z.array(z.string()).optional(),
});

const conflictSchema = z.object({
  id: z.string().min(1),
  field: z.string().min(1),
  values: z.array(z.string()).min(1),
  preferredValue: z.string().nullable(),
  resolution: z.string().min(1),
  userValidated: z.boolean(),
  impact: conflictImpactSchema,
  evidenceLevel: evidenceLevelSchema,
});

const jobMatchingSchema = z.object({
  enabled: z.boolean(),
  matchingWeights: z.object({
    technicalSkills: z.number(),
    experience: z.number(),
    seniority: z.number(),
    domain: z.number(),
    keywords: z.number(),
    projects: z.number(),
    languages: z.number(),
  }),
  minimumApplyScore: z.number(),
});

const jobProfileSchema = z.object({
  targetTitle: z.string(),
  matchScore: z.number().nullable(),
  matchedSkills: z.array(z.string()),
  missingSkills: z.array(z.string()),
  matchedExperience: z.array(z.string()),
  matchedProjects: z.array(z.string()),
  recommendedKeywords: z.array(z.string()),
  suppressedKeywords: z.array(z.string()),
  recommendedAchievements: z.array(z.string()),
  warnings: z.array(z.string()),
});

export const masterProfileSchema = z
  .object({
    schemaVersion: z.string().min(1),
    profile: z.object({
      fullName: z.string().min(1),
      professionalTitles: z.array(z.string()),
      contact: z.object({
        email: contactFieldSchema,
        phone: contactFieldSchema,
        linkedin: contactFieldSchema,
        location: contactFieldSchema,
      }),
      summary: z.string(),
      contactHistory: z
        .object({
          note: z.string(),
          previouslyDisplayed: z.object({
            email: z.string(),
            phone: z.string(),
            linkedin: z.string(),
            location: z.string(),
          }),
        })
        .optional(),
    }),
    targetRoles: z.array(
      z.object({
        id: z.string(),
        title: z.string(),
        priority: z.string(),
        keywords: z.array(z.string()),
        positioning: z.string(),
        sellingPoints: z.array(z.string()),
      }),
    ),
    skills: masterSkillsSchema,
    skillCatalog: z.array(skillSchema),
    experience: z.array(experienceSchema),
    projects: z.array(projectSchema),
    education: z.array(
      z.object({
        id: z.string(),
        degree: z.string(),
        institution: z.string(),
        startDate: optionalDate,
        endDate: optionalDate,
        graduationYear: z.number().int().nullable(),
        status: z.string(),
        evidenceLevel: evidenceLevelSchema,
        sourceCount: z.number(),
        userValidated: z.boolean(),
        sourceRefs: z.array(z.string()),
      }),
    ),
    certifications: z.array(
      z.object({
        id: z.string(),
        name: z.string(),
        issuer: z.string(),
        year: z.number().int().nullable(),
        status: z.string(),
        evidenceLevel: evidenceLevelSchema,
        sourceCount: z.number(),
        userValidated: z.boolean(),
        sourceRefs: z.array(z.string()),
      }),
    ),
    languages: z.array(
      z.object({
        id: z.string(),
        language: z.string(),
        level: z.string().nullable(),
        status: z.string(),
        evidenceLevel: evidenceLevelSchema,
        sourceCount: z.number(),
        userValidated: z.boolean(),
        conflicts: z.array(z.string()),
        sourceValues: z.array(z.string()).optional(),
        originalValues: z.record(z.string(), z.unknown()).optional(),
        sourceRefs: z.array(z.string()),
      }),
    ),
    metrics: z.array(metricSchema),
    skillAliases: z.record(
      z.string(),
      z.object({
        id: z.string(),
        canonical: z.string(),
        aliases: z.array(z.string()),
      }),
    ),
    skillAliasIndex: z.record(z.string(), z.string()),
    positioningProfiles: z.record(
      z.string(),
      z.object({
        id: z.string(),
        preferredTitle: z.string(),
        prioritySkills: z.array(z.string()),
        priorityExperience: z.array(z.string()),
        priorityExperienceLabels: z.array(z.string()).optional(),
        priorityProjects: z.array(z.string()),
        priorityProjectLabels: z.array(z.string()).optional(),
        secondarySkills: z.array(z.string()),
        sellingPoints: z.array(z.string()),
        avoidUnlessRelevant: z.array(z.string()),
        summaryFocus: z.array(z.string()),
        keywordStrategy: z.array(z.string()),
      }),
    ),
    conflicts: z.array(conflictSchema),
    careerTimeline: z.array(
      z.object({
        id: z.string(),
        experienceId: z.string(),
        company: z.string(),
        role: z.string(),
        roles: z.array(z.string()),
        startDate: z.union([isoYearOrMonth, z.null()]),
        endDate: z.union([isoYearOrMonth, z.null()]),
        dateStatus: z.string(),
        sourceValues: z.record(z.string(), z.unknown()),
        userValidated: z.boolean(),
        kind: z.string(),
        current: z.boolean().optional(),
      }),
    ),
    yearsOfExperience: z.object({
      value: z.number().nullable(),
      source: z.string().nullable(),
      status: z.string(),
      evidenceLevel: evidenceLevelSchema.optional(),
      sourceValues: z.array(z.string()).optional(),
      userValidated: z.boolean().optional(),
      note: z.string().optional(),
    }),
    userValidation: z.object({
      pending: z.array(z.string()),
      resolved: z.array(
        z.object({
          field: z.string(),
          previousValues: z.array(z.string()),
          resolvedValue: z.string(),
          resolvedAt: z.string(),
          source: z.literal("user"),
        }),
      ),
      lastUpdated: z.string().nullable(),
    }),
    jobMatching: jobMatchingSchema,
    jobProfile: jobProfileSchema,
    cvGenerationRules: z.object({
      neverInvent: z.boolean(),
      neverResolveConflictsAutomatically: z.boolean(),
      neverUseInferredAsFact: z.boolean(),
      preferUserValidated: z.boolean(),
      preferDocumentedEvidence: z.boolean(),
      adaptToJobDescription: z.boolean(),
      suppressIrrelevantSkills: z.boolean(),
      preserveCareerHistory: z.boolean(),
    }),
    evidenceRules: z.object({
      safeToClaimStatuses: z.array(z.string()),
      mentionOnlyStatuses: z.array(z.string()),
      historicalStatuses: z.array(z.string()),
      neverInvent: z.boolean(),
      neverResolveConflictsAutomatically: z.boolean(),
      neverUseInferredAsFact: z.boolean().optional(),
      preferUserValidated: z.boolean().optional(),
      userValidationPriority: z.array(z.string()).optional(),
    }),
    sources: z.array(
      z.object({
        id: z.string(),
        name: z.string(),
        type: z.string(),
        language: z.string(),
        scope: z.array(z.string()),
      }),
    ),
  })
  .superRefine((data, ctx) => {
    const collect = (items: Array<{ id: string }>, label: string) => {
      const seen = new Set<string>();
      for (const item of items) {
        if (seen.has(item.id)) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: `ID duplicado en ${label}: ${item.id}`,
          });
        }
        seen.add(item.id);
      }
    };

    collect(data.experience, "experience");
    collect(data.projects, "projects");
    collect(data.education, "education");
    collect(data.certifications, "certifications");
    collect(data.languages, "languages");
    collect(data.metrics, "metrics");
    collect(data.conflicts, "conflicts");
    collect(data.skillCatalog, "skillCatalog");
    collect(data.sources, "sources");
    collect(data.careerTimeline, "careerTimeline");
    collect(data.targetRoles, "targetRoles");

    for (const kind of MASTER_SKILL_KINDS) {
      const names = data.skills[kind] ?? [];
      const seen = new Set<string>();
      for (const name of names) {
        const key = name.trim().toLowerCase();
        if (!key) continue;
        if (seen.has(key)) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: `Skill duplicada en ${kind}: ${name}`,
          });
        }
        seen.add(key);
      }
    }
  });

export type MasterProfileValidation =
  | { ok: true; data: MasterProfile }
  | { ok: false; errors: string[] };

export function validateMasterProfile(input: unknown): MasterProfileValidation {
  const parsed = masterProfileSchema.safeParse(input);
  if (parsed.success) return { ok: true, data: parsed.data as MasterProfile };
  return {
    ok: false,
    errors: parsed.error.issues.map((i) => {
      const path = i.path.length ? i.path.join(".") : "(root)";
      return `${path}: ${i.message}`;
    }),
  };
}
