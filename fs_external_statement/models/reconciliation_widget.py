from odoo import models, fields, api
from odoo.osv import expression
from datetime import datetime

class AccountReconciliationWidget(models.AbstractModel):
    _inherit = 'account.reconciliation.widget'

    @api.model
    def get_move_lines_for_bank_statement_line(
            self, st_line_id, partner_id=None, excluded_ids=None, search_str=False, offset=0, limit=None, mode=None
    ):
        """
        Sobre escribe el metodo 'get_move_lines_for_bank_statement_line' y aplica una logica de ordenamiento por
        monto coincidente, fecha coincidente, monto ascendente solo si se envia el contexto 'dynamic_reconciliation'
        """
        move_lines = super(AccountReconciliationWidget, self).get_move_lines_for_bank_statement_line(
            st_line_id, partner_id=partner_id, excluded_ids=excluded_ids, search_str=search_str,
            offset=offset, limit=limit, mode=mode
        )
        if not self.env.context.get('dynamic_reconciliation'):
            return move_lines
        st_line = self.env['account.bank.statement.line'].browse(st_line_id)

        # Convertir st_line.date a date si es string
        st_date = st_line.date
        if isinstance(st_date, str):
            st_date = datetime.strptime(st_date, '%d/%m/%Y').date()

        # Ordenar move_lines con prioridad: monto coincidente, fecha coincidente, monto ascendente
        move_lines = sorted(
            move_lines,
            key=lambda l: (
                abs(l.get('debit', 0) - l.get('credit', 0)) != abs(st_line.amount),
                datetime.strptime(l.get('date'), '%d/%m/%Y').date() != st_date if isinstance(l.get('date'), str) else l.get('date') != st_date,
                abs(l.get('debit', 0) - l.get('credit', 0))
            )
        )
        return move_lines

    @api.model
    def _domain_move_lines_for_reconciliation(
            self, st_line, aml_accounts, partner_id, excluded_ids=None, search_str=False, mode='rp'
    ):
        """
        Sobre escribe el metodo '_domain_move_lines_for_reconciliation' y modifica el dominio agregandole:
        ('debit', '>', 0) o ('credit', '>', 0), ('payment_id', '!=', False) y ('parent_state', '=', 'draft')
        """
        domain = super(AccountReconciliationWidget, self)._domain_move_lines_for_reconciliation(
            st_line, aml_accounts, partner_id, excluded_ids or [], search_str, mode
        )
        if not self.env.context.get('dynamic_reconciliation'):
            return domain
        if st_line.amount > 0:
            amount_condition = ('debit', '>', 0)
        else:
            amount_condition = ('credit', '>', 0)
        domain = expression.AND([
            domain,
            [
                ('payment_id', '!=', False),
                amount_condition,
                ('parent_state', '=', 'draft')
            ]
        ])
        return domain