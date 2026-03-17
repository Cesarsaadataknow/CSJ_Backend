import { Filter, X } from "lucide-react";

/**
 * Datos mock de expedientes y carpetas.
 * TODO: Reemplazar por consumo del endpoint `GET /api/expedientes`
 * cuando el backend lo implemente.
 */
const MOCK_EXPEDIENTES = [
  { id: "08001225200420200000600JoseLaraOtrosWayuu", label: "08001225200420200000600JoseLaraOtrosWayuu" },
  { id: "08001225200420158405600Martires", label: "08001225200420158405600Martires" },
];

// Filtro de carpetas oculto por ahora. Descomentar para reactivar.
// const MOCK_CARPETAS = [
//   { id: "carp-001", label: "Cuaderno principal" },
//   { id: "carp-002", label: "Cuaderno de medidas cautelares" },
//   { id: "carp-003", label: "Cuaderno de pruebas" },
//   { id: "carp-004", label: "Incidente de nulidad" },
// ];

export interface ExpedienteFilterValues {
  expediente: string;
  carpeta: string;
}

interface ExpedienteFilterProps {
  values: ExpedienteFilterValues;
  onChange: (values: ExpedienteFilterValues) => void;
}

export function ExpedienteFilter({ values, onChange }: ExpedienteFilterProps) {
  const expedienteSeleccionado = MOCK_EXPEDIENTES.find((exp) => exp.id === values.expediente);
  const hayFiltroActivo = Boolean(values.expediente || values.carpeta);

  const limpiarFiltro = () => onChange({ expediente: "", carpeta: "" });

  return (
    <div className="flex flex-wrap items-center gap-4 px-1 py-1.5 text-sm">
      <Filter size={14} className="text-muted-foreground shrink-0" />

      <div className="flex flex-col gap-1 min-w-0 max-w-[420px]">
        <span className="text-xs font-medium text-muted-foreground">Expedientes</span>
        <select
          value={values.expediente}
          onChange={(e) => onChange({ ...values, expediente: e.target.value })}
          className="rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground outline-none focus:ring-1 focus:ring-ring w-full min-w-[280px]"
          aria-label="Seleccionar expediente"
        >
          <option value="">— Seleccionar —</option>
          {MOCK_EXPEDIENTES.map((exp) => (
            <option key={exp.id} value={exp.id}>
              {exp.label}
            </option>
          ))}
        </select>
        {expedienteSeleccionado && (
          <span className="text-xs text-muted-foreground break-all" title={expedienteSeleccionado.label}>
            Expediente: {expedienteSeleccionado.label}
          </span>
        )}
      </div>

      {/* Filtro de carpetas oculto por ahora. Descomentar para reactivar.
      <select
        value={values.carpeta}
        onChange={(e) => onChange({ ...values, carpeta: e.target.value })}
        className="rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground outline-none focus:ring-1 focus:ring-ring max-w-[260px] truncate"
        aria-label="Seleccionar carpeta"
      >
        <option value="">Todas las carpetas</option>
        {MOCK_CARPETAS.map((carp) => (
          <option key={carp.id} value={carp.id}>
            {carp.label}
          </option>
        ))}
      </select>
      */}

      {hayFiltroActivo && (
        <button
          type="button"
          onClick={limpiarFiltro}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          title="Quitar expediente y carpeta seleccionados"
        >
          <X size={14} aria-hidden />
          Limpiar filtro
        </button>
      )}
    </div>
  );
}
