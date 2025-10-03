from odoo import models, fields, api
from odoo.exceptions import UserError


class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    trade_header_id = fields.Many2one('trade.header', string='Cabecera de Comercio (Extracto)')
    settlement_number = fields.Char(
        string='Número de Liquidación',
        required=True,
        tracking=True,
        index=True,
        help="Número único de liquidación"
    )
    account_bank_statement_trailer_tax_ids = fields.One2many(
        'account.bank.settlement.trailer.tax',
        'statement_id',
        string='Trailers de Liquidaciónes (Impuestos)'
    )
    tax_invoice_id = fields.Many2one('account.move', string='Factura de Impuesto')
    transfer_id = fields.Many2one('account.payment', string='Transferencia a Banco')
    tax_total_amount = fields.Float(string='Monto Total de Impuestos', compute='_compute_tax_amount', store=True)
    net_balance_end = fields.Float(string='Balance Final Neto', compute='_compute_net_balance_end', store=True)

    def cancel_lines(self):
        """
        Metódo encargado de cancelar todas las cociliaciones
        """
        for rec in self:
            rec.line_ids.filtered('journal_entry_ids').cancel_reconciliation()
            #Borrar la transferencia
            transfer_id = rec.transfer_id
            if transfer_id:
                transfer_id.action_draft()
                transfer_id.unlink()
            # Borrar la factura de impuestos
            tax_invoice_id = rec.tax_invoice_id
            if tax_invoice_id:
                # Borro el pago
                aml_with_matches = self.env['account.move.line'].search([
                    ('move_id', '=', tax_invoice_id.id),
                    ('matched_debit_ids', '!=', False)
                ])
                if len(aml_with_matches) > 1:
                    raise UserError(
                        f"El pago relacionado a la factura {tax_invoice_id.name} tiene más de una línea contable conciliada. "
                        f"No se permite más de una."
                    )
                for aml in aml_with_matches:
                    if len(aml.matched_debit_ids) > 1:
                        raise UserError(
                            f"La línea contable {aml.name} de la factura {tax_invoice_id.name} tiene más de un pago conciliado. "
                            f"No se permite más de uno."
                        )
                matched_debit = aml_with_matches.mapped('matched_debit_ids')[:1] if aml_with_matches else False
                payment_group_ids = matched_debit.debit_move_id.move_id.line_ids.mapped('payment_id.payment_group_id')
                unique_payment_groups = list(set(payment_group_ids))

                if len(unique_payment_groups) > 1:
                    raise UserError(
                        f'Se encontraron {len(unique_payment_groups)} Payment Groups asociados al mismo débito: '
                        f'{", ".join(pg.name for pg in unique_payment_groups if pg)}. '
                        'Esto no está permitido.'
                    )
                payment_group_id = unique_payment_groups[0] if unique_payment_groups else False
                if payment_group_id:
                    payment_group_id.action_draft()
                    payment_group_id.unlink()

                # Borro la factura
                tax_invoice_id.button_draft()
                tax_invoice_id.button_cancel()
                tax_invoice_id.delete_number()
                tax_invoice_id.unlink()

    # Métodos Base
    def create_bank_statement_by_trade_header(
            self, trade_header_id, trade_header_name,
            settlement_number, journal_id, journal_name, transaction_detail_ids
    ):
        """
        Metodo encargado de crear un 'account.bank.statement' desde 'trade.header'
        """
        statement_vals = {
            'name': f"{trade_header_name} - {settlement_number} - {journal_name}",
            'journal_id': journal_id,
            'date': fields.Date.today(),
            'balance_start': 0.0,
            'balance_end_real': sum(transaction_detail_ids.mapped('total')),
            'settlement_number': settlement_number,
            'trade_header_id': trade_header_id
        }
        bank_statement_id = self.create(statement_vals)
        return bank_statement_id.id

    # Métodos Depend
    @api.depends('account_bank_statement_trailer_tax_ids.total')
    def _compute_tax_amount(self):
        """Computa el campo tax_total_amount correspondiente al total de los impuestos"""
        for record in self:
            record.tax_total_amount = sum(
                record.account_bank_statement_trailer_tax_ids
                    .filtered(lambda x: x.parent_type == 'net')
                    .mapped('total')
            )

    @api.depends('tax_total_amount', 'balance_end')
    def _compute_net_balance_end(self):
        """
        Computa el campo net_balance_end correspondiente al balance entre el total de las transacciones y los impuestos
        """
        for record in self:
            record.net_balance_end = record.balance_end - record.tax_total_amount

    def action_bank_reconcile_bank_statements(self):
        """
        Sobrescritura del metodo 'action_bank_reconcile_bank_statements' del modulo 'account'
        """
        super_return = super(AccountBankStatement, self).action_bank_reconcile_bank_statements()
        statement_line_non_reconciled_ids = []
        bank_stmt_lines = self.env['account.bank.statement.line'].browse(super_return['context']['statement_line_ids'])
        for bank_stmt_line in bank_stmt_lines:
            payment_id = self.env['account.payment'].search([
                ('terminal', '=', bank_stmt_line.terminal),
                ('card_last_number', '=', bank_stmt_line.last_four_digits_card),
                ('batch', '=', bank_stmt_line.batch),
                ('coupon', '=', bank_stmt_line.coupon),
                ('payment_date', '=', bank_stmt_line.date),
                ('amount', '=', bank_stmt_line.amount),
                ('journal_id', '=', bank_stmt_line.statement_id.journal_id.id),
                ('state', '=', 'posted'),
                ('move_line_ids.debit', '>', 0),
                ('move_line_ids.parent_state', '=', 'draft')
            ])
            if len(payment_id) > 1:
                raise UserError(
                    'Error en la conciliación no pueden haber dos pagos iguales en los siguientes campos: '
                    'terminal, card_last_number, batch, coupon, payment_date, amount, journal_id, state.'
                )
            if payment_id:
                debit_move_lines = payment_id.move_line_ids.filtered(
                    lambda l: l.debit > 0 and l.parent_state == 'draft'
                )
                for move_line in debit_move_lines:
                    bank_stmt_line.process_reconciliation(payment_aml_rec=move_line)
            else:
                statement_line_non_reconciled_ids.append(bank_stmt_line.id)
        super_return['context']['statement_line_ids'] = statement_line_non_reconciled_ids
        return super_return

    def _apply_general_validations(self):
        """Validaciones generales del metodo 'action_apply_taxes_and_transfer_bank'"""
        self.ensure_one()
        if not self.journal_id:
            raise UserError('El extracto bancario dede tener un "Diario" relacionado')

        non_reconcile_journal_id = self.journal_id.non_reconcile_journal_id
        if not non_reconcile_journal_id:
            raise UserError('El diario relacionado a el extracto debe tener un "Diario de No Conciliación" relacionado')
        if non_reconcile_journal_id.post_at == 'bank_rec':
            raise UserError('El "Diario de No Conciliación" no puede ser del tipo "Conciliación Bancaria"')

    def _apply_transfer_bank_validations(self):
        """Validaciones del metodo _apply_transfer_bank"""
        if not self.journal_id.bank_journal_id:
            raise UserError('El diario relacionado a el extracto debe tener un "Diario del Banco" relacionado')

    def _apply_transfer_bank(self):
        """Función encargada de hacer la transferencia entre el diario de tarjeta y el diario del Banco"""
        self._apply_transfer_bank_validations()
        account_payment_vals = {
            'amount': self.net_balance_end,
            'payment_date': self.date,
            'journal_id': self.journal_id.non_reconcile_journal_id.id,
            'destination_journal_id': self.journal_id.bank_journal_id.id,
            'payment_type': 'transfer',
            'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
        }
        new_transfer = self.env['account.payment'].create(account_payment_vals)
        new_transfer.post()
        self.write({'transfer_id': new_transfer.id})

    def _apply_taxes_validations(self):
        """Validaciones del metodo _apply_taxes"""
        if not self.journal_id.partner_id:
            raise UserError('El diario relacionado a el extracto debe tener un "Contacto del Banco" relacionado')

    def _apply_tax_trailer_validations(self, trailer):
        """Validaciones propias del procesamiento de los trailer de impuestos"""
        settlement_tax_id = trailer.settlement_tax_id
        if not settlement_tax_id:
            raise UserError('El trailer debe tener un "Impuesto" relacionado')

        if settlement_tax_id.type == 'tax':
            if not settlement_tax_id.parent_id:
                raise UserError('El impuesto debe tener un "Impuesto Padre" relacionado')
            if not settlement_tax_id.tax_id:
                raise UserError('El impuesto debe tener un "Impuesto" relacionado')
        if settlement_tax_id.type == 'net' and not settlement_tax_id.product_id:
            raise UserError('El impuesto debe tener un "Producto" relacionado')

    def _apply_taxes(self):
        """
        Genera una factura de proveedor al contacto asociado al diario de la tarjeta, con el fin de registrar
        y ejecutar el pago de los impuestos/servicios correspondientes desde la cuenta vinculada a la tarjeta.
        """
        self._apply_taxes_validations()
        invoice_lines = []
        # Crea las lineas de la factura
        for trailer in filter(lambda x: x.settlement_tax_id.type == 'net', self.account_bank_statement_trailer_tax_ids):
            self._apply_tax_trailer_validations(trailer)
            product_tmpl_id = trailer.settlement_tax_id.product_id
            product = self.env['product.product'].search(
                [('product_tmpl_id', '=', product_tmpl_id.id)], limit=2
            )
            if len(product) > 1:
                raise UserError(f'El producto {product_tmpl_id.name} (ID: {product_tmpl_id.id}) debe ser único')

            if trailer.total != 0:
                tax_list = []
                trailer_total = trailer.total
                for trailer_tax in filter(
                    lambda x: x.settlement_tax_id.type == 'tax'
                              and x.settlement_tax_id.parent_id.id == trailer.settlement_tax_id.id,
                    self.account_bank_statement_trailer_tax_ids
                ):
                    self._apply_tax_trailer_validations(trailer_tax)
                    if trailer_tax.total != 0:
                        settlement_tax_id = trailer_tax.settlement_tax_id
                        tax_list.append(settlement_tax_id.tax_id.id)
                        settlement_tax_id.tax_id.write({'amount': trailer_tax.total})
                        trailer_total = trailer_total - trailer_tax.total
                invoice_lines.append(
                    (
                        0, 0,
                        {
                            'product_id': product.id, 'price_unit': trailer_total,
                            'tax_ids': [(6, 0, tax_list)]
                        }
                    )
                )


        # Crea la factura misma
        account_move_vals = {
            'partner_id': self.journal_id.partner_id.id,
            'l10n_latam_document_number': f'1-{self.settlement_number}',
            'l10n_latam_document_type_id': self.env.ref('l10n_ar.dc_a_f').id,
            'type': 'in_invoice',
            'invoice_date': self.date,
            'journal_id': self.env.ref('fs_external_statement.account_journal_card_tax').id,
            'invoice_line_ids': invoice_lines
        }
        new_account_move = self.env['account.move'].create(account_move_vals)
        # Publica la factura
        new_account_move.action_post(ignore_confirmation=True)
        # Relaciona el extracto con la factura creada
        self.write({'tax_invoice_id': new_account_move.id})
        # Le aplica el pago a la factura
        account_payment_group_vals = {
            'partner_id': new_account_move.partner_id.id,
            'partner_type': 'supplier',
            'retencion_ganancias': 'no_aplica',
            'to_pay_amount': new_account_move.amount_residual,
            'payment_date': self.date,
            'company_id': self.company_id.id,
            'payment_ids': [(0, 0, {
                'amount': new_account_move.amount_residual,
                'payment_date': self.date,
                'journal_id': self.journal_id.non_reconcile_journal_id.id,
                'payment_type': 'outbound',
                'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                'partner_type': 'supplier',
                'partner_id': new_account_move.partner_id.id,
            })],
            'to_pay_move_line_ids': [(6, 0, new_account_move.mapped('open_move_line_ids').ids)],
        }
        account_payment_group = self.env['account.payment.group'].create(account_payment_group_vals)
        account_payment_group.post()

    def action_apply_taxes_and_transfer_bank(self):
        """
        Acción encargada de generar una factura por los impuestos y de hacer la transferencia bancaria del monto restante
        """
        self._apply_general_validations()
        self._apply_taxes()
        self._apply_transfer_bank()

    def button_open_reconciliation_report(self):
        """
        Función encargada de mostrar el reporte de conciliación
        """
        self.ensure_one()
        return {
            'name': 'Reporte de Conciliación',
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'view_mode': 'tree',
            'views': [(self.env.ref('fs_external_statement.view_bank_statement_line_tree_reconciled_state').id, 'tree')],
            'domain': [('statement_id', '=', self.id)],
        }