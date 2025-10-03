from odoo import models, fields, api
from odoo.tools.misc import formatLang
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    # Campos Base
    batch = fields.Char(string="Batch")
    terminal = fields.Char(string="Terminal")
    last_four_digits_card = fields.Char(string="Last Four Digits of Card")
    coupon = fields.Char(string="Coupon")

    # Campos Relacionales
    external_statement_transaction_detail_id = fields.Many2one('transaction.detail', string='Detalle de la transacción (Extracto Externos)')

    # Campos Calculados
    total_payment_amount = fields.Float(compute='_compute_total_payment_amount', string='Total Pagos', store=True)
    payment_names = fields.Html(compute='_compute_payment_names', string='Pagos Relacionados', store=True, default="")
    difference_amount = fields.Float(compute='_compute_difference_amount', string='Diferencia', store=True)
    reconciled = fields.Boolean(string='Esta conciliado?', compute='_compute_reconciled', store=True)

    # Métodos Base

    def cancel_reconciliation(self):
        """
        Metodo utilizado para descon
        """
        payments = set()
        for move_line in self.journal_entry_ids:
            payments.add(move_line.payment_id)
        for payment in payments:
            payment_group_id = payment.payment_group_id
            payment_group_id.action_draft()
            payment_group_id.post()
        self.button_cancel_reconciliation()
        self.write({
            'partner_id': False
        })

    def create_bank_statement_line_by_trade_header(
            self, transaction_id, transaction_operation_date, transaction_cover_terminal_posnet,
            transaction_summary_lot_posnet, transaction_card_number, transaction_coupon_posnet, transaction_total, bank_statement_id
    ):
        """
        Metodo encargado de crear la line del extracto bancario desde el modelo 'trade.header'
        """
        line_vals = {
            'date': transaction_operation_date or fields.Date.today(),
            'name': f'Terminal: {transaction_cover_terminal_posnet or "N/A"} - '
                    f'Lote: {transaction_summary_lot_posnet or "N/A"} - '
                    f'Tarjeta: {transaction_card_number or "N/A"}',
            'amount': transaction_total or 0.0,
            'batch': str(transaction_summary_lot_posnet or ""),
            'terminal': str(transaction_cover_terminal_posnet or ''),
            'last_four_digits_card': str(transaction_card_number.strip()[-4:]) if transaction_card_number else '',
            'coupon': transaction_coupon_posnet or '',
            'statement_id': bank_statement_id,
            'external_statement_transaction_detail_id': transaction_id
        }
        bank_statement_line_id = self.create(line_vals)
        return bank_statement_line_id.id

    # Métodos Depends
    @api.depends('journal_entry_ids')
    def _compute_reconciled(self):
        """
        Marca como conciliado cuando tiene 'account.move.line' relacionados
        """
        for record in self:
            record.reconciled = True if record.journal_entry_ids else False

    @api.depends('amount', 'total_payment_amount')
    def _compute_difference_amount(self):
        """
        Calcula la diferencia restante entre el extracto y las relaciones de 'account.move.line'
        """
        for record in self:
            record.difference_amount = record.total_payment_amount - record.amount

    @api.depends('journal_entry_ids')
    def _compute_payment_names(self):
        """Computa el campo Html 'payment_names' cuando se modifique un 'journal_entry_ids'"""
        for record in self:
            payment_name_list = []
            processed_move_ids = set()
            move_line_ids = record.journal_entry_ids
            for move_line_id in move_line_ids:
                move = move_line_id.move_id.id
                if move not in processed_move_ids:
                    processed_move_ids.add(move)
                    amount_formatted = formatLang(
                        record.env,
                        move_line_id.payment_id.amount,
                        currency_obj=move_line_id.payment_id.currency_id
                    )
                    if move_line_id.payment_id.payment_group_id:
                        name = move_line_id.payment_id.payment_group_id.name
                    else:
                        name = move_line_id.move_name
                    _logger.info(
                        f"[DEBUG] move_line: {move_line_id.id}, "
                        f"payment_id: {move_line_id.payment_id.id}, "
                        f"payment_group_id: {move_line_id.payment_id.payment_group_id.id if move_line_id.payment_id.payment_group_id else None}, "
                        f"move_name: {move_line_id.move_name}"
                    )

                    payment_name_list.append(
                        f'<strong>{name}</strong> - {amount_formatted}<br/>({move_line_id.payment_id.name})'
                    )
            record.payment_names = '<br/>'.join(payment_name_list)

    @api.depends('journal_entry_ids')
    def _compute_total_payment_amount(self):
        """
        Calcula el total de los pagos relacionados
        """
        for record in self:
            payments = record.journal_entry_ids.mapped('payment_id')
            record.total_payment_amount = sum(p.amount for p in payments)

    # Metodos Action
    def action_print_selected_lines(self):
        """Action para imprimir el pdf del detalle de conciliación"""
        return self.env.ref('fs_external_statement.report_bank_statement_line_pdf').report_action(self)

