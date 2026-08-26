import { Dropdown } from "@web/core/dropdown/dropdown";
import { StockValuationReportLine } from "@stock_account/stock_valuation/line/line";

/**
 * Mejora 2 (tarea 64440): habilita el menú de los "3 puntitos" en las líneas del
 * reporte de valuación.
 *
 * La línea no necesita una prop nueva: el menú se arma desde ``props.line`` (el
 * objeto de datos que ya recibe), donde el controller deja el array
 * ``drilldowns`` con ``{label, onSelected}``. Así la sección de Variación —que
 * de fábrica no es clickeable— pasa a ofrecer navegación al detalle sin tocar el
 * componente de línea del core.
 */
StockValuationReportLine.components = {
    ...StockValuationReportLine.components,
    Dropdown,
};
