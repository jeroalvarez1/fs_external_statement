odoo.define('fs_external_statement.reconciliation_patch', function (require) {
    "use strict";

    const StatementRenderer = require('account.ReconciliationRenderer').StatementRenderer;
    var qweb = require('web.core').qweb;
    var time = require('web.time');
    var session = require('web.session');

    StatementRenderer.include({
        /**
         * Sobrescritura completa de showRainbowMan sin botones
         */
        showRainbowMan: function (state) {
            var dt = Date.now() - this.time;

            // Modificamos la plantilla QWeb para quitar los botones
            var originalQwebRender = qweb.render;
            qweb.render = function(template, context) {
                if (template === "reconciliation.done") {
                    // Eliminamos la sección de botones del contexto
                    var modifiedContext = Object.assign({}, context);
                    modifiedContext.context = null; // Esto evita que se renderice la sección de botones
                    return originalQwebRender.call(this, template, modifiedContext);
                }
                return originalQwebRender.apply(this, arguments);
            };

            var $done = $(qweb.render("reconciliation.done", {
                'duration': moment(dt).utc().format(time.getLangTimeFormat()),
                'number': state.valuenow,
                'timePerTransaction': Math.round(dt/1000/state.valuemax),
                'context': state.context,
                'bank_statement_id': state.bank_statement_id,
            }));

            // Restauramos la función original
            qweb.render = originalQwebRender;

            $done.find('*').addClass('o_reward_subcontent');

            // Eliminamos cualquier botón que pueda haber sido renderizado
            $done.find('.button_close_statement, .button_back_to_statement').remove();

            if (session.show_effect) {
                this.trigger_up('show_effect', {
                    type: 'rainbow_man',
                    fadeout: 'no',
                    message: $done,
                });
                this.$el.css('min-height', '450px');
            } else {
                $done.appendTo(this.$el);
            }

            var activeId = parseInt(window.location.hash.match(/active_id=(\d+)/)[1]);

            // Tu acción personalizada
            this.do_action({
                type: 'ir.actions.act_window',
                res_model: 'account.bank.statement',
                res_id: activeId,
                views: [[false, 'form']],
            });
        }
    });
});