import { patch } from "@web/core/utils/patch";
import { useSetupAction } from "@web/search/action_hook";
import { StockValuationReport } from "@stock_account/stock_valuation/stock_valuation_report";

/**
 * Mantiene los filtros del reporte al ir y volver del detalle (tarea 64440).
 *
 * El client action se desmonta al navegar al drill-down y se vuelve a montar al
 * volver por el breadcrumb, así que el estado del controller —y con él los
 * filtros y la fecha— se perdía: el usuario entraba a ver cómo se compone una
 * cuenta y al volver el reporte estaba sin filtrar.
 *
 * El action service ya provee el mecanismo para esto: antes de dejar la acción
 * llama a ``getLocalState`` y al volver pasa lo exportado en ``props.state``
 * (para client actions el env recibe ``__getLocalState__``, ver
 * ``action_service.js``). Guardamos ahí los filtros y los restauramos ANTES del
 * primer render, aprovechando que el ``onWillStart`` del componente nativo —que
 * es el que dispara la carga de datos— corre después de todos los setup.
 */
patch(StockValuationReport.prototype, {
    setup() {
        super.setup();
        this._restoreValuationState();
        useSetupAction({
            getLocalState: () => ({ valuationState: this._exportValuationState() }),
        });
    },

    _exportValuationState() {
        const state = this.controller.state;
        return {
            date: state.date,
            productIds: [...(state.productIds || [])],
            categIds: [...(state.categIds || [])],
            costMethods: [...(state.costMethods || [])],
            valuations: [...(state.valuations || [])],
            lineTypes: [...(state.lineTypes || [])],
        };
    },

    _restoreValuationState() {
        const saved = this.props.state?.valuationState;
        if (!saved) {
            return;
        }
        // ``date`` se guarda como el objeto luxon tal cual: el estado exportado
        // queda en memoria (no se serializa), así que no hace falta reconstruirlo.
        Object.assign(this.controller.state, saved);
    },
});
