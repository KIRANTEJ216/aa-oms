// @caoms/shared — constants, shared validators (zod ↔ pydantic)
// Re-export for web and api (api can import via copy or npm link in prod)

export const ROLES = ["Super Admin","Firm Admin","Partner","Manager","Article Assistant","Paid Assistant","Client"] as const;
export type Role = typeof ROLES[number];

export const CLIENT_TYPES = ["Individual","HUF","Company","LLP","Trust"] as const;
export const TASK_TYPES = ["Statutory","Client","Internal","Recurring"] as const;
export const TASK_PRIORITIES = ["High","Medium","Low"] as const;
export const TASK_STATUSES = ["Not Started","In Progress","Pending Information","Under Review","Completed","Overdue"] as const;
export const COMPLIANCE_CODES = ["GSTR1","GSTR3B","GSTR9","ITR_NON_AUDIT","ITR_AUDIT","TDS_26Q","ADV_TAX","ROC_MGT7","ROC_AOC4"] as const;

export const PAN_REGEX = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
export const GSTIN_REGEX = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9]Z[0-9A-Z]$/;
export const TAN_REGEX = /^[A-Z]{4}[0-9]{5}[A-Z]$/;

export const FOLDERS = ["KYC Documents","Financial Statements","Tax Documents","GST Documents","Correspondence","Agreements","Bank Documents"] as const;
export const INVOICE_TYPES = ["Tax Invoice","Proforma Invoice","Credit Note","Debit Note","Receipt"] as const;

export const SEED_TENANT = { slug: "aarav-advisors", name: "Aarav Advisors" };
