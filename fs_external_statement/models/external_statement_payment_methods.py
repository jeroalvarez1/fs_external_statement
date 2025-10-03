from odoo import models, fields

class ExternalStatementPaymentMethods(models.Model):
    _name = 'external.statement.payment.methods'
    _description = 'External Statement Payment Methods'

    name = fields.Char(string='Name', required=True)
    description = fields.Char(string='Description', required=True)
    journal_id = fields.Many2one('account.journal', string='Journal')