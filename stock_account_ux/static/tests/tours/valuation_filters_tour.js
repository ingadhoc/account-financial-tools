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

// Stock Move Types only applies to stock moves: picking a type leaves Movement Type
// on Stock Moves alone, and going back to Product Value clears the types.
registry.category("web_tour.tours").add("stock_account_ux_valuation_stock_move_types", {
    url: "/odoo/stock-valuation-closing",
    steps: () => [
        {
            trigger: "#filter_line_types button",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item:contains('Product Value')",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item.selected:contains('Product Value')",
        },
        {
            trigger: "#filter_stock_move_types button",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item:contains('Scrap')",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item.selected:contains('Scrap')",
        },
        {
            trigger: "#filter_line_types button",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item.selected:contains('Stock Moves')",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item:not(.selected):contains('Product Value')",
            run: "click",
        },
        {
            trigger: "#filter_stock_move_types button",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item:not(.selected):contains('Scrap')",
        },
    ],
});
