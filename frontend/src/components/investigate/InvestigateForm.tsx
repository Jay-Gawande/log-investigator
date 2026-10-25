"use client";

import { Button, Card, Field, Spinner, inputCls } from "@/components/ui";

export type FormValues = { description: string; start: string; end: string };

export type Preset = { label: string; onClick: () => void; disabled?: boolean };

export function InvestigateForm({
  values,
  onChange,
  onSubmit,
  pending,
  errors,
  presets,
}: {
  values: FormValues;
  onChange: (next: FormValues) => void;
  onSubmit: () => void;
  pending: boolean;
  errors: Record<string, string>;
  presets: Preset[];
}) {
  return (
    <Card>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
        className="space-y-4"
        noValidate
      >
        <Field label="What happened?" htmlFor="description" error={errors.description} hint="A short description of the incident, in your own words.">
          <textarea
            id="description"
            rows={3}
            className={inputCls}
            placeholder="Users reported checkout failures around 2 PM"
            value={values.description}
            onChange={(e) => onChange({ ...values, description: e.target.value })}
          />
        </Field>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="From" htmlFor="start" error={errors.start}>
            <input
              id="start"
              type="datetime-local"
              className={inputCls}
              value={values.start}
              onChange={(e) => onChange({ ...values, start: e.target.value })}
            />
          </Field>
          <Field label="To" htmlFor="end" error={errors.end}>
            <input
              id="end"
              type="datetime-local"
              className={inputCls}
              value={values.end}
              onChange={(e) => onChange({ ...values, end: e.target.value })}
            />
          </Field>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" disabled={pending}>
            {pending && <Spinner />}
            {pending ? "Investigating" : "Investigate"}
          </Button>
          <span className="text-xs text-slate-500">Presets:</span>
          {presets.map((p) => (
            <Button key={p.label} type="button" variant="secondary" disabled={p.disabled || pending} onClick={p.onClick}>
              {p.label}
            </Button>
          ))}
        </div>
      </form>
    </Card>
  );
}
