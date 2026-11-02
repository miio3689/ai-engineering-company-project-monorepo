"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { createIncident, IncidentServiceError } from "@/services/incidents";
import {
  INCIDENT_BRANCHES,
  INCIDENT_CATEGORIES,
  INCIDENT_ORIGINS,
  INCIDENT_STATUSES,
  type IncidentCategory,
  type IncidentCreateInput,
  type IncidentFieldErrors,
  type IncidentFormField,
  type IncidentOrigin,
  type IncidentStatus,
} from "@/types/incident";

interface FormValues {
  title: string;
  description: string;
  category: IncidentCategory | "";
  status: IncidentStatus;
  origin: IncidentOrigin;
  branch: (typeof INCIDENT_BRANCHES)[number]["value"];
}

const INITIAL_VALUES: FormValues = {
  title: "",
  description: "",
  category: "",
  status: "open",
  origin: "customer",
  branch: "central",
};

const fieldClass = "min-h-11 w-full rounded-lg border border-gray-400 bg-white px-3 py-2 text-base focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700";

export default function IncidentRegisterForm() {
  const [values, setValues] = useState<FormValues>(INITIAL_VALUES);
  const [fieldErrors, setFieldErrors] = useState<IncidentFieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    const firstError = Object.keys(fieldErrors)[0] as IncidentFormField | undefined;
    if (!firstError) return;
    const control = formRef.current?.elements.namedItem(firstError);
    if (control instanceof HTMLElement) control.focus();
  }, [fieldErrors]);

  function updateField<Field extends keyof FormValues>(
    field: Field,
    value: FormValues[Field],
  ) {
    setValues((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => {
      const next = { ...current };
      delete next[field as IncidentFormField];
      return next;
    });
    setError(null);
    setSuccess(null);
  }

  function validate(): IncidentFieldErrors {
    const errors: IncidentFieldErrors = {};
    if (!values.title.trim()) errors.title = "Introduce el título de la incidencia.";
    if (!values.description.trim()) {
      errors.description = "Describe brevemente la incidencia.";
    }
    if (!values.category) errors.category = "Selecciona una categoría.";
    if (!values.status) errors.status = "Selecciona un estado.";
    if (!values.origin) errors.origin = "Selecciona el origen.";
    if (!values.branch) errors.branch = "Selecciona una sede.";
    return errors;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) return;
    setError(null);
    setSuccess(null);

    const validationErrors = validate();
    if (Object.keys(validationErrors).length) {
      setFieldErrors(validationErrors);
      setError("Revisa los campos señalados antes de guardar.");
      return;
    }

    setFieldErrors({});
    setIsSubmitting(true);
    const input: IncidentCreateInput = {
      title: values.title.trim(),
      description: values.description.trim(),
      category: values.category as IncidentCategory,
      status: values.status,
      origin: values.origin,
      branch: values.branch,
    };

    try {
      await createIncident(input);
      setValues(INITIAL_VALUES);
      setFieldErrors({});
      setSuccess("La incidencia se registró correctamente.");
    } catch (caught) {
      if (caught instanceof IncidentServiceError) {
        setFieldErrors(caught.fieldErrors);
        setError(caught.message);
      } else {
        setError("No se pudo registrar la incidencia. Inténtalo de nuevo.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function fieldDescription(field: IncidentFormField) {
    return fieldErrors[field] ? `${field}-error` : undefined;
  }

  return (
    <section
      className="rounded-2xl border border-orange-200 bg-white p-5 shadow-sm sm:p-8"
      aria-labelledby="incident-register-title"
    >
      <h2 id="incident-register-title" className="mb-5 text-xl font-bold">
        Datos de la incidencia
      </h2>
      <form ref={formRef} noValidate onSubmit={submit}>
        <fieldset
          disabled={isSubmitting}
          className="grid gap-5 disabled:opacity-70 sm:grid-cols-2"
          aria-busy={isSubmitting}
        >
          <legend className="sr-only">Formulario de registro de incidencia</legend>
          <label className="grid gap-2 font-semibold sm:col-span-2" htmlFor="incident-title">
            Título *
            <input
              id="incident-title"
              name="title"
              value={values.title}
              onChange={(event) => updateField("title", event.target.value)}
              className={fieldClass}
              required
              aria-invalid={Boolean(fieldErrors.title)}
              aria-describedby={fieldDescription("title")}
            />
            {fieldErrors.title && (
              <span id="title-error" className="font-normal text-red-800">
                {fieldErrors.title}
              </span>
            )}
          </label>

          <label className="grid gap-2 font-semibold sm:col-span-2" htmlFor="incident-description">
            Descripción *
            <textarea
              id="incident-description"
              name="description"
              value={values.description}
              onChange={(event) => updateField("description", event.target.value)}
              className={`${fieldClass} min-h-32`}
              rows={5}
              required
              aria-invalid={Boolean(fieldErrors.description)}
              aria-describedby={fieldDescription("description")}
            />
            {fieldErrors.description && (
              <span id="description-error" className="font-normal text-red-800">
                {fieldErrors.description}
              </span>
            )}
          </label>

          <label className="grid gap-2 font-semibold" htmlFor="incident-category">
            Categoría *
            <select
              id="incident-category"
              name="category"
              value={values.category}
              onChange={(event) => updateField(
                "category",
                INCIDENT_CATEGORIES.find((option) => option.value === event.target.value)?.value ?? "",
              )}
              className={fieldClass}
              required
              aria-invalid={Boolean(fieldErrors.category)}
              aria-describedby={fieldDescription("category")}
            >
              <option value="">Selecciona una categoría</option>
              {INCIDENT_CATEGORIES.map(({ value, label }) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            {fieldErrors.category && (
              <span id="category-error" className="font-normal text-red-800">
                {fieldErrors.category}
              </span>
            )}
          </label>

          <label className="grid gap-2 font-semibold" htmlFor="incident-status">
            Estado *
            <select
              id="incident-status"
              name="status"
              value={values.status}
              onChange={(event) => updateField(
                "status",
                INCIDENT_STATUSES.find((option) => option.value === event.target.value)?.value ?? "open",
              )}
              className={fieldClass}
              required
              aria-invalid={Boolean(fieldErrors.status)}
              aria-describedby={fieldDescription("status")}
            >
              {INCIDENT_STATUSES.map(({ value, label }) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            {fieldErrors.status && (
              <span id="status-error" className="font-normal text-red-800">
                {fieldErrors.status}
              </span>
            )}
          </label>

          <label className="grid gap-2 font-semibold" htmlFor="incident-origin">
            Origen *
            <select
              id="incident-origin"
              name="origin"
              value={values.origin}
              onChange={(event) => updateField(
                "origin",
                INCIDENT_ORIGINS.find((option) => option.value === event.target.value)?.value ?? "customer",
              )}
              className={fieldClass}
              required
              aria-invalid={Boolean(fieldErrors.origin)}
              aria-describedby={fieldDescription("origin")}
            >
              {INCIDENT_ORIGINS.map(({ value, label }) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            {fieldErrors.origin && (
              <span id="origin-error" className="font-normal text-red-800">
                {fieldErrors.origin}
              </span>
            )}
          </label>

          <label
            className={`grid gap-2 rounded-xl border p-3 font-semibold transition-colors ${
              values.origin === "branch"
                ? "border-orange-600 bg-orange-50"
                : "border-transparent"
            }`}
            htmlFor="incident-branch"
          >
            Sede *
            <select
              id="incident-branch"
              name="branch"
              value={values.branch}
              onChange={(event) => updateField(
                "branch",
                INCIDENT_BRANCHES.find((option) => option.value === event.target.value)?.value ?? "central",
              )}
              className={fieldClass}
              required
              aria-invalid={Boolean(fieldErrors.branch)}
              aria-describedby={fieldDescription("branch")}
            >
              {INCIDENT_BRANCHES.map(({ value, label }) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            {values.origin === "branch" && (
              <span className="font-normal text-orange-900">
                Indica la sede desde la que se reporta la incidencia.
              </span>
            )}
            {fieldErrors.branch && (
              <span id="branch-error" className="font-normal text-red-800">
                {fieldErrors.branch}
              </span>
            )}
          </label>

          <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex min-h-11 items-center justify-center rounded-lg bg-orange-700 px-5 font-semibold text-white hover:bg-orange-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? "Guardando incidencia…" : "Registrar incidencia"}
            </button>
            {isSubmitting && (
              <span role="status" className="text-sm text-gray-700">
                Enviando los datos…
              </span>
            )}
          </div>
        </fieldset>

        {error && (
          <p role="alert" className="mt-5 rounded-lg border border-red-300 bg-red-50 p-4 text-red-900">
            {error}
          </p>
        )}
        {success && (
          <p role="status" className="mt-5 rounded-lg border border-green-300 bg-green-50 p-4 text-green-900">
            {success}
          </p>
        )}
      </form>
    </section>
  );
}
