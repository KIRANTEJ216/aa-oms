import { z } from "zod";

export const loginSchema = z.object({ email: z.string().email(), password: z.string().min(8) });
export const registerSchema = loginSchema.extend({ name: z.string().min(2), mobile: z.string().min(10) });
export const mfaSchema = z.object({ code: z.string().length(6) });

// PAN: ABCDE1234F
export const PAN_REGEX = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
// GSTIN: 15 chars: 2 state + 5 alpha + 4 num + 1 alpha + 1 alpha/num + Z + 1 alpha/num
export const GSTIN_REGEX = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z$/;
// TAN: AAAA12345A
export const TAN_REGEX = /^[A-Z]{4}[0-9]{5}[A-Z]$/;

export const clientSchema = z.object({
  type: z.enum(["Individual", "HUF", "Company", "LLP", "Trust"]),
  name: z.string().min(2),
  pan: z.string().regex(PAN_REGEX, "Invalid PAN"),
  gstin: z.string().regex(GSTIN_REGEX, "Invalid GSTIN").optional().or(z.literal("")),
  tan: z.string().regex(TAN_REGEX, "Invalid TAN").optional().or(z.literal("")),
  email: z.string().email(),
  mobile: z.string().min(10),
  address: z.string().min(5),
  dob_or_incorporation: z.string().min(8),
  engagement_manager: z.string().min(2),
  services: z.array(z.string()).default([]),
  is_portal_enabled: z.boolean().default(false),
});
export type LoginInput = z.infer<typeof loginSchema>;
export type ClientInput = z.infer<typeof clientSchema>;

// ── Tasks ───────────────────────────────────────────────────────
export const taskSchema = z.object({
  type: z.enum(["Statutory", "Client", "Internal", "Recurring"]),
  title: z.string().min(2).max(200),
  description: z.string().max(2000).optional().default(""),
  priority: z.enum(["High", "Medium", "Low"]).default("Medium"),
  status: z.enum(["Not Started", "In Progress", "Pending Information", "Under Review", "Completed"]).default("Not Started"),
  due_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Use YYYY-MM-DD"),
  assignee_id: z.string().optional(),
  client_id: z.string().optional(),
  reminder_days: z.array(z.number().int()).default([7, 3, 1]),
  recurrence_pattern: z.enum(["Daily", "Weekly", "Monthly", "Quarterly", "Annually"]).optional().nullable(),
  recurrence_end_condition: z.string().optional().nullable(),
});
export type TaskInput = z.infer<typeof taskSchema>;

// ── Compliance Filings ──────────────────────────────────────────
export const COMPLIANCE_CODES = [
  "GSTR1", "GSTR3B", "GSTR9",
  "ITR_NON_AUDIT", "ITR_AUDIT",
  "TDS_26Q", "ADV_TAX",
  "ROC_MGT7", "ROC_AOC4",
] as const;

export const filingSchema = z.object({
  client_id: z.string().min(1),
  compliance_code: z.enum(COMPLIANCE_CODES),
  period: z.string().min(1),
  actual_due_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Use YYYY-MM-DD"),
  notes: z.string().optional(),
});
export type FilingInput = z.infer<typeof filingSchema>;
