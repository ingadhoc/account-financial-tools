import { registry } from "@web/core/registry";

// Mejora 2 (tarea 64440): la sección "Stock Variation" no ofrecía ninguna
// navegación al detalle. El tour comprueba en un browser real que la línea de
// cuenta muestra el menú de los "3 puntitos" y que una de sus opciones abre la
// lista del detalle.
registry.category("web_tour.tours").add("stock_account_ux_valuation_drilldown", {
    url: "/odoo/stock-valuation-closing",
    steps: () => [
        {
            content: "La sección de Variación está renderizada",
            trigger: "tr:contains('Stock Variation')",
        },
        {
            content: "La línea de cuenta de la Variación ofrece el menú de drill-down",
            trigger: "tr.line_level_2 .o_valuation_line_drilldown button",
            run: "click",
        },
        {
            content: "El menú lista los dos orígenes de la diferencia sin contabilizar",
            trigger: ".o-dropdown--menu .dropdown-item:contains('Unaccounted Value Adjustments')",
        },
        {
            content: "Abrir el detalle de los movimientos sin contabilizar",
            trigger: ".o-dropdown--menu .dropdown-item:contains('Unaccounted Stock Moves')",
            run: "click",
        },
        {
            content: "Se abrió la lista de movimientos",
            trigger: ".o_list_view",
        },
    ],
});

// Los filtros tienen que sobrevivir a la ida y vuelta al detalle: el client action
// se desmonta al navegar y se remonta al volver por el breadcrumb.
registry.category("web_tour.tours").add("stock_account_ux_valuation_filters_kept", {
    url: "/odoo/stock-valuation-closing",
    steps: () => [
        {
            content: "Filtrar por método de valuación",
            trigger: "#filter_cost_methods button",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item:contains('Average')",
            run: "click",
        },
        {
            content: "El filtro quedó aplicado",
            trigger: ".o-dropdown--menu .dropdown-item.selected:contains('Average')",
        },
        {
            content: "Cerrar el dropdown",
            trigger: "h1, .o_control_panel",
            run: "click",
        },
        {
            content: "Ir al detalle de una cuenta de la Variación",
            trigger: "tr.line_level_2 .o_valuation_line_drilldown button",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item:contains('Unaccounted Stock Moves')",
            run: "click",
        },
        {
            content: "Estamos en el detalle",
            trigger: ".o_list_view",
        },
        {
            content: "Volver al reporte por el breadcrumb",
            trigger: ".breadcrumb-item:not(.active) a, .o_breadcrumb .o_back_button",
            run: "click",
        },
        {
            content: "El reporte volvió a renderizarse",
            trigger: "tr:contains('Stock Variation')",
        },
        {
            content: "...y el filtro sigue aplicado",
            trigger: "#filter_cost_methods button",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item.selected:contains('Average')",
        },
    ],
});
