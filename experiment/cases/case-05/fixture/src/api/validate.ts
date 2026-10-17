import type { NextFunction, Request, Response } from "express";

type Rule = { type: "string"; maxLength?: number; oneOf?: readonly string[] } | { type: "boolean" };
export type Schema = Record<string, Rule & { optional?: boolean }>;

/** Validates req.body against a flat schema; responds 400 with field errors. */
export function validate(schema: Schema) {
  return (req: Request, res: Response, next: NextFunction) => {
    const body = req.body ?? {};
    const errors: Record<string, string> = {};
    for (const [field, rule] of Object.entries(schema)) {
      const v = body[field];
      if (v === undefined) {
        if (!rule.optional) errors[field] = "required";
        continue;
      }
      if (rule.type === "boolean" && typeof v !== "boolean") errors[field] = "must be boolean";
      if (rule.type === "string") {
        if (typeof v !== "string") errors[field] = "must be string";
        else if (rule.maxLength && v.length > rule.maxLength) errors[field] = `max length ${rule.maxLength}`;
        else if (rule.oneOf && !rule.oneOf.includes(v)) errors[field] = `must be one of ${rule.oneOf.join(", ")}`;
      }
    }
    if (Object.keys(errors).length > 0) {
      return res.status(400).json({ error: { code: "invalid_request", fields: errors } });
    }
    next();
  };
}
