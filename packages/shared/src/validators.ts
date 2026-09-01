import { z } from "zod";
import { PAN_REGEX, GSTIN_REGEX } from "./index";
export const panSchema = z.string().regex(PAN_REGEX, "Invalid PAN");
export const gstinSchema = z.string().regex(GSTIN_REGEX, "Invalid GSTIN").optional().or(z.literal(""));
