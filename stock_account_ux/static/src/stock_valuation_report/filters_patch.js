import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { StockValuationReportFilters } from "@stock_account/stock_valuation/filters/filters";

// Sumar los componentes usados por los nuevos dropdowns de filtros.
StockValuationReportFilters.components = {
    ...StockValuationReportFilters.components,
    Dropdown,
    DropdownItem,
    MultiRecordSelector,
};

/**
 * Agrega a la barra de filtros del reporte (Mejora 1, tarea 64440) los
 * controles de Producto, Categoría, Método de valuación, Tipo de valuación y
 * Tipo de movimiento. Producto/Categoría usan MultiRecordSelector; el resto son
 * dropdowns de selección múltiple (DropdownItem con check).
 */
patch(StockValuationReportFilters.prototype, {
    setup() {
        super.setup();
        // Suscribir ESTE componente al estado del controller con su propio
        // useState: env.controller viene atado al render del padre, así que sin
        // esto los cambios de filtro no re-renderizan la barra (la selección no
        // "prevalecía"). Con useState propio, tocar un filtro re-renderiza acá.
        this._controller = useState(this.env.controller);
    },

    get controller() {
        return this._controller;
    },

    // -- Producto / Categoría (MultiRecordSelector) ---------------------------
    get productSelectorProps() {
        return {
            resModel: "product.product",
            resIds: this.controller.state.productIds || [],
            update: (resIds) => this.controller.setProductIds(resIds),
            placeholder: _t("Products"),
        };
    },

    get categSelectorProps() {
        return {
            resModel: "product.category",
            resIds: this.controller.state.categIds || [],
            update: (resIds) => this.controller.setCategIds(resIds),
            placeholder: _t("Product Categories"),
        };
    },

    // -- Opciones estáticas de los dropdowns multi-selección ------------------
    get costMethodOptions() {
        return [
            { value: "standard", label: _t("Standard Price") },
            { value: "fifo", label: _t("First In First Out (FIFO)") },
            { value: "average", label: _t("Average Cost (AVCO)") },
        ];
    },

    get valuationOptions() {
        return [
            { value: "periodic", label: _t("Manual / Periodic") },
            { value: "real_time", label: _t("Automated / Perpetual") },
        ];
    },

    get lineTypeOptions() {
        return [
            { value: "stock_move", label: _t("Stock Moves") },
            { value: "product_value", label: _t("Product Value") },
        ];
    },

    // -- Estado / handlers ----------------------------------------------------
    isFilterSelected(key, value) {
        return (this.controller.state[key] || []).includes(value);
    },

    onCostMethodToggle(value) {
        return this.controller.toggleCostMethod(value);
    },

    onValuationToggle(value) {
        return this.controller.toggleValuation(value);
    },

    onLineTypeToggle(value) {
        return this.controller.toggleLineType(value);
    },
});
