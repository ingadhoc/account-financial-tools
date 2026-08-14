import { registry } from "@web/core/registry";

// Tour de diagnóstico/regresión (tarea 64440): al elegir un método de valuación
// la selección debe persistir (checkmark) sin cerrar el dropdown.
registry.category("web_tour.tours").add("stock_account_ux_valuation_filters", {
    url: "/odoo/stock-valuation-closing",
    steps: () => [
        {
            trigger: "#filter_cost_methods button",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item:contains('FIFO')",
            run: "click",
        },
        {
            // closingMode='none' mantiene el menú abierto; con la reactividad
            // arreglada, FIFO queda marcado como seleccionado.
            trigger: ".o-dropdown--menu .dropdown-item.selected:contains('FIFO')",
        },
    ],
});
