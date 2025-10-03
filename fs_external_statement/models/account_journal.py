from odoo import api, fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    partner_id = fields.Many2one(
        'res.partner',
        string='Contacto del Banco',
        help='Contacto utilizado para registrar los impuesto en la conciliación bancaria'
    )
    non_reconcile_journal_id = fields.Many2one(
        'account.journal',
        string='Diario de No Conciliación',
        help='Diario utilizado para registrar los impuesto en la conciliación bancaria'
    )
    bank_journal_id =fields.Many2one(
        'account.journal',
        string='Diario del Banco',
        help='Diario utilizado para hacer la transferencia hacia el diario Bancario'
    )

    settlement_tax_ids = fields.Many2many(
        'settlement.tax',
        'journal_settlement_tax_rel',
        'journal_id',
        'settlement_tax_id',
        string='Impuestos sobre la liquidación'
    )

    @api.onchange('post_at')
    def _onchange_partner_id(self):
        if self.post_at == 'pay_val':
            self.partner_id = False

    @api.onchange('post_at')
    def _onchange_non_reconcile_journal_id(self):
        if self.post_at == 'pay_val':
            self.non_reconcile_journal_id = False

    @api.onchange('post_at')
    def _onchange_bank_journal_id(self):
        if self.post_at == 'pay_val':
            self.bank_journal_id = False