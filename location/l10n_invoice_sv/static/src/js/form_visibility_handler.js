odoo.define('l10n_invoice_sv.form_visibility_handler', function (require) {
    "use strict";

    const {patch} = require('web.utils');
    const FormRenderer = require('web.FormRenderer');

    console.log("✅ form_visibility_handler.js cargado");

    patch(FormRenderer.prototype, {
        _updateView() {
            this._super(...arguments);
            this._toggleRetencionFields();
        },

        _toggleRetencionFields() {
            const codigo = this.state.data.codigo_tipo_documento;
            const show = (codigo === '03');

            // Reintento para que el DOM esté listo
            setTimeout(() => {
                this.el.querySelectorAll('.field-iva-percibido, .field-iva-percibido-amount, .field-campo-test')
                    .forEach(el => {
                        el.closest('.o_field_widget').style.display = show ? '' : 'none';
                    });
            }, 100);
        }
    });
});