import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { serializeDate } from "@web/core/l10n/dates";
import { StockValuationReportController } from "@stock_account/stock_valuation/controller";

const { DateTime } = luxon;

/**
 * Extiende el controller del Reporte de Valuación de Inventario (Mejora 1,
 * tarea 64440) para sostener el estado de los 5 filtros y propagarlos al
 * backend. Sin filtros seleccionados, el backend delega en el estándar (AC4).
 */
patch(StockValuationReportController.prototype, {
    /**
     * Inicializa (lazy) las claves de filtros sobre el ``state`` reactivo. Se
     * llama antes del primer render (desde loadReportData en onWillStart), así
     * el Proxy reactivo registra las claves y los getters de Filters reaccionan.
     */
    _valuationFilterState() {
        const state = this.state;
        state.productIds ??= [];
        state.categIds ??= [];
        state.costMethods ??= [];
        state.valuations ??= [];
        state.lineTypes ??= [];
        return state;
    },

    // "Hoy = sin corte" lo decide el cliente, único lugar con un solo reloj: el server lo
    // comparaba contra el tz del usuario y adentro del offset no coinciden (ticket 126535).
    get reportDate() {
        const date = serializeDate(this.state.date);
        return date === serializeDate(DateTime.now()) ? false : date;
    },

    // Reimplementación de loadReportData (copia de stock_account v19.0) para
    // sumar los filtros como kwargs del get_report_values. La preparación de
    // líneas es idéntica a la nativa.
    async loadReportData() {
        const state = this._valuationFilterState();
        const kwargs = {
            date: this.reportDate,
            product_ids: state.productIds,
            categ_ids: state.categIds,
            cost_methods: state.costMethods,
            valuations: state.valuations,
            line_types: state.lineTypes,
        };
        const res = await this.orm.call(
            "stock_account.stock.valuation.report",
            "get_report_values",
            [],
            kwargs
        );
        this.data = res.data;
        // Prepare the "Inventory Loss" lines.
        if (this.data.inventory_loss) {
            for (const line of this.data.inventory_loss.lines) {
                line.account = this.data.accounts_by_id[line.account_id];
            }
        }
        // Prepare "Stock Variation" lines.
        for (const line of this.data.stock_variation.lines) {
            line.account = this.data.accounts_by_id[line.account_id];
            // Mejora 2: la Variación no ofrecía ninguna navegación al detalle.
            // Se le cuelga el menú de los "3 puntitos" con los orígenes de la
            // diferencia sin contabilizar que TIENEN algo para mostrar (el
            // backend los marca en ``drilldown_types``).
            line.drilldowns = this._variationDrilldowns(line);
        }
        // Prepare the "Initial Balance" lines.
        this.data.initial_balance.lines = [];
        for (let [accountId, data] of Object.entries(this.data.initial_balance.lines_by_account_id)) {
            const account = this.data.accounts_by_id[accountId];
            this.data.initial_balance.lines.push({
                label: account.display_name,
                value: data.value,
                account_id: accountId,
                // Mejora 2 (AC2): la línea de cuenta abre el Libro Mayor de ESA
                // cuenta hasta la fecha del reporte. El nativo solo navegaba
                // desde el total, con todas las cuentas juntas.
                method: () => this._openAccountLedger(accountId),
            });
        }
        // Prepare the "Ending Stock" lines.
        this.data.ending_stock.lines = [];
        for (let [accountId, data] of Object.entries(this.data.ending_stock.lines_by_account_id)) {
            const account = this.data.accounts_by_id[accountId];
            this.data.ending_stock.lines.push({
                label: account?.display_name,
                value: data.value,
                account_id: accountId,
            });
        }
        return res;
    },

    // -- Drill-down del Balance inicial (Mejora 2, AC2) -----------------------
    async _openAccountLedger(accountId) {
        const action = await this.orm.call(
            "stock_account.stock.valuation.report",
            "action_open_account_ledger",
            [accountId, this.state.date.toISODate() || false]
        );
        return this.actionService.doAction(action);
    },

    // -- Drill-down de la Variación (Mejora 2) --------------------------------
    /**
     * Opciones del menú de los "3 puntitos" de una línea de cuenta de la
     * Variación: los orígenes de la diferencia sin contabilizar que tienen
     * registros para mostrar.
     *
     * El backend decide (``drilldown_types``), porque es el que sabe qué
     * productos cuelgan de la cuenta y qué queda pendiente. Sin tipos no se
     * devuelve nada y la línea no dibuja el menú: es el caso de la línea de la
     * cuenta de contrapartida, que no tiene detalle propio para abrir.
     */
    /**
     * Mapa de los orígenes de la Variación: etiqueta y método backend de cada
     * uno. Getter propio para que un módulo agregue un origen extendiendo el
     * mapa en vez de reescribir ``_variationDrilldowns``, espejo de
     * ``_get_drilldown_checks`` en Python (tarea 58212):
     *
     *     get variationDrilldownByType() {
     *         return { ...super.variationDrilldownByType, currency_revaluation: {...} };
     *     }
     */
    get variationDrilldownByType() {
        return {
            stock_move: {
                label: _t("Unaccounted Stock Moves"),
                method: "action_open_variation_stock_moves",
            },
            product_value: {
                label: _t("Unaccounted Value Adjustments"),
                method: "action_open_variation_product_values",
            },
        };
    },

    _variationDrilldowns(line) {
        const drilldownByType = this.variationDrilldownByType;
        return (line.drilldown_types || [])
            .filter((lineType) => lineType in drilldownByType)
            .map((lineType) => ({
                label: drilldownByType[lineType].label,
                onSelected: () =>
                    this._openVariationDetail(drilldownByType[lineType].method, line.account_id),
            }));
    },

    /**
     * El dominio lo arma el backend, que es el que sabe qué productos cuelgan de
     * la cuenta de la línea. Se le pasan los filtros activos del reporte para que
     * el detalle respete el mismo scope que el importe que se clickeó (AC6).
     */
    async _openVariationDetail(method, accountId) {
        const state = this._valuationFilterState();
        const action = await this.orm.call(
            "stock_account.stock.valuation.report",
            method,
            [accountId, this.reportDate],
            {
                filters: {
                    product_ids: state.productIds,
                    categ_ids: state.categIds,
                    cost_methods: state.costMethods,
                    valuations: state.valuations,
                },
            }
        );
        return this.actionService.doAction(action);
    },

    // -- Setters / toggles de filtros (cada uno recarga, como setDate) --------
    setProductIds(resIds) {
        this._valuationFilterState().productIds = resIds;
        return this.loadReportData();
    },

    setCategIds(resIds) {
        this._valuationFilterState().categIds = resIds;
        return this.loadReportData();
    },

    toggleValuationFilterValue(key, value) {
        const state = this._valuationFilterState();
        const current = state[key];
        state[key] = current.includes(value)
            ? current.filter((v) => v !== value)
            : [...current, value];
        return this.loadReportData();
    },

    toggleCostMethod(value) {
        return this.toggleValuationFilterValue("costMethods", value);
    },

    toggleValuation(value) {
        return this.toggleValuationFilterValue("valuations", value);
    },

    toggleLineType(value) {
        return this.toggleValuationFilterValue("lineTypes", value);
    },

    // Generar el asiento respetando TODOS los filtros activos (Mejora 1, tarea
    // 64440): con filtros de producto el backend arma un cierre parcial acotado a
    // esos productos, y con "Movement Type" lo acota al origen filtrado de la
    // variación (solo movimientos de stock, o solo ajustes de valor), dejando la
    // otra porción pendiente.
    async actionGenerateEntry() {
        const state = this._valuationFilterState();
        const kwargs = {
            product_ids: state.productIds,
            categ_ids: state.categIds,
            cost_methods: state.costMethods,
            valuations: state.valuations,
            line_types: state.lineTypes,
        };
        const args = [[this.companyId]];
        const date = serializeDate(this.state.date);
        if (date != serializeDate(DateTime.now())) {
            args.push(date);
        }
        const action = await this.orm.call(
            "res.company",
            "action_close_stock_valuation",
            args,
            kwargs
        );
        if (action) {
            this.actionService.doAction(action);
        }
    },
});
