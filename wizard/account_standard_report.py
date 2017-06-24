# -*- coding: utf-8 -*-

import calendar
import time

from datetime import datetime, timedelta
from odoo import api, models, fields, _
from odoo.tools import float_is_zero
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT


D_LEDGER = {'general': {'name': _('General Ledger'),
                        'group_by': 'account_id',
                        'model': 'account.account',
                        'short': 'code',
                        },
            'partner': {'name': _('Partner Ledger'),
                        'group_by': 'partner_id',
                        'model': 'res.partner',
                        'short': 'name',
                        },
            'journal': {'name': _('Journal Ledger'),
                        'group_by': 'journal_id',
                        'model': 'account.journal',
                        'short': 'code',
                        },
            'open': {'name': _('Open Ledger'),
                     'group_by': 'account_id',
                     'model': 'account.account',
                     'short': 'code',
                     },
            'aged': {'name': _('Aged Balance'),
                     'group_by': 'partner_id',
                     'model': 'res.partner',
                     'short': 'name',
                     },
            }


class AccountStandardLedgerPeriode(models.TransientModel):
    _name = 'account.report.standard.ledger.periode'

    name = fields.Char('Name')
    date_from = fields.Datetime('Date from')
    date_to = fields.Datetime('Date to')


class AccountStandardLedgerLines(models.TransientModel):
    _name = 'account.report.standard.ledger.report'

    name = fields.Char()


class AccountStandardLedgerLines(models.TransientModel):
    _name = 'account.report.standard.ledger.line'
    _order = 'type,date,id'  # ,move_id,account_id

    report_id = fields.Many2one('account.report.standard.ledger.report')
    account_id = fields.Many2one('account.account')
    type = fields.Selection([('0_init', 'Initial'), ('1_init_line', 'Init Line'), ('2_line', 'Line'), ('3_compact', 'Compacted'), ('4_total', 'Total')], string='Type')
    journal_id = fields.Many2one('account.journal')
    partner_id = fields.Many2one('res.partner')
    group_by_key = fields.Integer()
    move_id = fields.Many2one('account.move')
    date = fields.Date()
    date_maturity = fields.Date()
    debit = fields.Float()
    credit = fields.Float()
    balance = fields.Float()
    cumul_balance = fields.Float()
    full_reconcile_id = fields.Many2one('account.full.reconcile')
    reconciled = fields.Boolean()


class AccountStandardLedger(models.TransientModel):
    _name = 'account.report.standard.ledger'
    _description = 'Account Standard Ledger'

    def _get_periode_date(self):
        lang_code = self.env.user.lang or 'en_US'
        date_format = self.env['res.lang']._lang_get(lang_code).date_format

        today_year = fields.datetime.now().year

        last_day = self.company_id.fiscalyear_last_day or 31
        last_month = self.company_id.fiscalyear_last_month or 12
        periode_obj = self.env['account.report.standard.ledger.periode']
        periode_obj.search([]).unlink()
        periode_ids = periode_obj
        for year in range(today_year, today_year - 4, -1):
            date_from = datetime(year - 1, last_month, last_day) + timedelta(days=1)
            date_to = datetime(year, last_month, last_day)
            user_periode = "%s - %s" % (date_from.strftime(date_format),
                                        date_to.strftime(date_format),
                                        )
            vals = {
                'name': user_periode,
                'date_from': date_from.strftime(DEFAULT_SERVER_DATE_FORMAT),
                'date_to': date_to.strftime(DEFAULT_SERVER_DATE_FORMAT), }
            periode_ids += periode_obj.create(vals)
        return False

    name = fields.Char()
    type_ledger = fields.Selection([('general', 'General Ledger'), ('partner', 'Partner Ledger'), ('journal', 'Journal Ledger'), ('open', 'Open Ledger'), ('aged', 'Aged Balance')], string='Type', default='general', required=True,
                                   help=' * General Ledger : Journal entries group by account\n'
                                   ' * Partner Leger : Journal entries group by partner, with only payable/recevable accounts\n'
                                   ' * Journal Ledger : Journal entries group by journal, without initial balance\n'
                                   ' * Open Ledger : Openning journal at Start date\n')
    summary = fields.Boolean('Trial Balance', default=False,
                             help=' * Check : generate a trial balance.\n'
                             ' * Uncheck : detail report.\n')
    amount_currency = fields.Boolean("With Currency", help="It adds the currency column on report if the currency differs from the company currency.")
    reconciled = fields.Boolean('With Reconciled Entries', default=True,
                                help='Only for entrie with a payable/receivable account.\n'
                                ' * Check this box to see un-reconcillied and reconciled entries with payable.\n'
                                ' * Uncheck to see only un-reconcillied entries. Can be use only with parnter ledger.\n')
    partner_select_ids = fields.Many2many(comodel_name='res.partner', string='Partners', domain=['|', ('is_company', '=', True), ('parent_id', '=', False)], help='If empty, get all partners')
    account_methode = fields.Selection([('include', 'Include'), ('exclude', 'Exclude')], string="Methode")
    account_in_ex_clude = fields.Many2many(comodel_name='account.account', string='Accounts', help='If empty, get all accounts')
    sum_group_by_top = fields.Boolean('Sum on Top', default=False, help='See the sum of element on top.')
    sum_group_by_bottom = fields.Boolean('Sum on Bottom', default=True, help='See the sum of element on top.')
    init_balance_history = fields.Boolean('Initial balance with history.', default=True,
                                          help=' * Check this box if you need to report all the debit and the credit sum before the Start Date.\n'
                                          ' * Uncheck this box to report only the balance before the Start Date\n')
    company_id = fields.Many2one('res.company', string='Company', readonly=True, default=lambda self: self.env.user.company_id)
    journal_ids = fields.Many2many('account.journal', string='Journals', required=True, default=lambda self: self.env['account.journal'].search([]),
                                   help='Select journal, for the Open Ledger you need to set all journals.')
    date_from = fields.Date(string='Start Date', help='Use to compute initial balance.')
    date_to = fields.Date(string='End Date', help='Use to compute the entrie matched with futur.')
    target_move = fields.Selection([('posted', 'All Posted Entries'),
                                    ('all', 'All Entries'),
                                    ], string='Target Moves', required=True, default='posted')
    periode_date = fields.Many2one('account.report.standard.ledger.periode', 'Periode', default=_get_periode_date, help="Auto complete Start and End date.")
    month_selec = fields.Selection([(1, '01 Junary'), (2, '02 Febuary'), (3, '03 March'), (4, '04 April'), (5, '05 May'), (6, '06 June'),
                                    (7, '07 Jully'), (8, '08 August'), (9, '09 September'), (10, '10 October'), (11, '11 November'), (12, '12 December')],
                                   string='Month')
    result_selection = fields.Selection([('customer', 'Customer'),
                                         ('supplier', 'Supplier'),
                                         ('customer_supplier', 'Receivable and Payable Accounts')
                                         ], string="Partner's", required=True, default='supplier')
    report_name = fields.Char('Report Name')
    compact_account = fields.Boolean('Compacte account.', default=False)
    reset_exp_acc_start_date = fields.Boolean('Reset expenses/revenue account at start date', default=True)
    # lines_ids = fields.One2many('account.report.standard.ledger.line', 'report_id', string='Lines')
    report_id = fields.Many2one('account.report.standard.ledger.report')
    account_ids = fields.Many2many('account.account', relation='table_standard_report_accounts')
    partner_ids = fields.Many2many('res.partner', relation='table_standard_report_partner')

    @api.onchange('account_in_ex_clude')
    def on_change_summary(self):
        if self.account_in_ex_clude:
            self.account_methode = 'include'
        else:
            self.account_methode = False

    @api.onchange('type_ledger')
    def on_change_type_ledger(self):
        if self.type_ledger in ('partner', 'journal', 'open', 'aged'):
            self.compact_account = False
        if self.type_ledger == 'aged':
            self.date_from = False
        if self.type_ledger not in ('partner', 'aged',):
            self.reconciled = True
            return {'domain': {'account_in_ex_clude': []}}
        self.account_in_ex_clude = False
        return {'domain': {'account_in_ex_clude': [('type_third_parties', 'in', ('customer', 'supplier'))]}}

    @api.onchange('periode_date')
    def on_change_periode_date(self):
        if self.periode_date:
            self.date_from = self.periode_date.date_from
            self.date_to = self.periode_date.date_to
            if self.month_selec:
                self.on_change_month_selec()

    @api.onchange('month_selec')
    def on_change_month_selec(self):
        if self.periode_date and self.month_selec:
            date_from = datetime.strptime(self.periode_date.date_from, DEFAULT_SERVER_DATETIME_FORMAT)
            date_from = datetime(date_from.year, self.month_selec, 1)
            date_to = datetime(date_from.year, self.month_selec, calendar.monthrange(date_from.year, self.month_selec)[1])
            self.date_from = date_from.strftime(DEFAULT_SERVER_DATE_FORMAT)
            self.date_to = date_to.strftime(DEFAULT_SERVER_DATE_FORMAT)
        elif self.periode_date and not self.month_selec:
            self.on_change_periode_date()

    def action_view_lines(self):
        self.ensure_one()
        self.report_id = self.env['account.report.standard.ledger.report'].create({})
        self.compute_data()
        return {
            'name': _("Ledger Lines"),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.report.standard.ledger.line',
            'type': 'ir.actions.act_window',
            'domain': "[('report_id','=',%s)]" % (self.report_id.id),
            'target': 'current',
        }

    def print_pdf_report(self):
        self.ensure_one()
        self.report_id = self.env['account.report.standard.ledger.report'].create({})
        self.compute_data()
        return {
            'name': _("Ledger Lines"),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.report.standard.ledger.line',
            'type': 'ir.actions.act_window',
            'domain': "[('report_id','=',%s)]" % (self.report_id.id),
            'target': 'current',
        }

        return self.env['report'].with_context(landscape=True).get_action(self, 'account_standard_report.report_account_standard_report', data={'active_id': self.id})

    def print_excel_report(self):
        self.ensure_one()
        return self.env['report'].get_action(self, 'account_standard_report.report_account_standard_excel')

    def pre_compute_form(self):
        if self.type_ledger in ('partner', 'journal', 'open', 'aged'):
            self.compact_account = False
            self.reset_exp_acc_start_date = False
        if self.type_ledger == 'aged':
            self.date_from = False
        if self.type_ledger not in ('partner', 'aged',):
            self.reconciled = True
            self.partner_select_ids = False
        self.account_ids = self._search_account()
        print(self.account_ids)

    def compute_data(self):
        t = time.time()
        self.account_ids = self._search_account()
        self.partner_ids = self._search_partner()
        self._get_name_report()
        # self.lines_ids.unlink()
        if self.type_ledger != 'open':
            self._sql_unaffected_earnings()
        print(t - time.time())
        self._sql_init_balance()
        print(t - time.time())
        self._sql_init_unreconcillied_table()
        print(t - time.time())
        if self.type_ledger != 'open':
            self._sql_lines()
        print(t - time.time())
        if self.compact_account:
            self._sql_lines_compacted()
        print(t - time.time())
        if self.type_ledger in ('general',):
            self._sql_account_total()
        elif self.type_ledger in ('partner', 'aged'):
            self._sql_partner_total()
        print(t - time.time())
        self.refresh()
        print(t - time.time())

    def _sql_unaffected_earnings(self):
        company = self.company_id
        unaffected_earnings_account = self.env['account.account'].search([('company_id', '=', company.id), ('user_type_id', '=', self.env.ref('account.data_unaffected_earnings').id)], limit=1)
        if unaffected_earnings_account not in self.account_ids:
            return

        query = """
        INSERT INTO account_report_standard_ledger_line
            (report_id, create_uid, create_date, account_id, type, date, debit, credit, balance, cumul_balance)
        SELECT
            %s AS report_id,
            %s AS create_uid,
            NOW() AS create_date,
            %s AS account_id,
            '0_init' AS type,
            %s AS date,
            CASE WHEN %s THEN COALESCE(SUM(account_move_line.debit), 0) ELSE CASE WHEN COALESCE(sum(account_move_line.balance), 0) <= 0 THEN 0 ELSE COALESCE(sum(account_move_line.balance), 0) END END AS debit,
            CASE WHEN %s THEN COALESCE(SUM(account_move_line.credit), 0) ELSE CASE WHEN COALESCE(sum(account_move_line.balance), 0) >= 0 THEN 0 ELSE COALESCE(sum(account_move_line.balance), 0) END END AS credit,
            COALESCE(SUM(account_move_line.balance), 0) AS balance,
            COALESCE(SUM(account_move_line.balance), 0) AS cumul_balance
        FROM
            account_move_line
            LEFT JOIN account_account acc ON (account_move_line.account_id = acc.id)
            LEFT JOIN account_account_type acc_type ON (acc.user_type_id = acc_type.id)
            LEFT JOIN account_move m ON (account_move_line.move_id = m.id)
        WHERE
            m.state IN %s
            AND account_move_line.company_id = %s
            AND account_move_line.date < %s
            AND acc_type.include_initial_balance = FALSE
        """

        params = [
            self.report_id.id,
            self.env.uid,
            unaffected_earnings_account.id,
            self.date_from,
            self.init_balance_history,
            self.init_balance_history,
            ('posted',) if self.target_move == 'posted' else ('posted', 'draft',),
            company.id,
            self.date_from, ]

        self.env.cr.execute(query, tuple(params))

    def _sql_init_balance(self):
        company = self.company_id
        # initial balance partner
        query = """
        INSERT INTO account_report_standard_ledger_line
            (report_id, create_uid, create_date, account_id, partner_id, group_by_key, type, date, debit, credit, balance)

        WITH matching_in_futur_before_init (id) AS
        (
        SELECT DISTINCT
            afr.id
        FROM
            account_full_reconcile afr
        INNER JOIN account_move_line aml ON aml.full_reconcile_id=afr.id
        WHERE
            aml.company_id = %s
            AND aml.date >= %s
        )
        SELECT
            %s AS report_id,
            %s AS create_uid,
            NOW() AS create_date,
            CASE WHEN %s THEN MIN(account_move_line.account_id) ELSE NULL END,
            CASE WHEN %s THEN MIN(account_move_line.partner_id) ELSE NULL END,
            (CASE
                WHEN %s THEN account_move_line.account_id
                ELSE account_move_line.partner_id
            END) AS group_by_key,
            '0_init' AS type,
            %s AS date,
            CASE WHEN %s THEN COALESCE(SUM(account_move_line.debit), 0) ELSE CASE WHEN COALESCE(sum(account_move_line.balance), 0) <= 0 THEN 0 ELSE COALESCE(sum(account_move_line.balance), 0) END END AS debit,
            CASE WHEN %s THEN COALESCE(SUM(account_move_line.credit), 0) ELSE CASE WHEN COALESCE(sum(account_move_line.balance), 0) >= 0 THEN 0 ELSE COALESCE(sum(account_move_line.balance), 0) END END AS credit,
            COALESCE(SUM(account_move_line.balance), 0) AS balance
        FROM
            account_move_line
            LEFT JOIN account_account acc ON (account_move_line.account_id = acc.id)
            LEFT JOIN account_account_type acc_type ON (acc.user_type_id = acc_type.id)
            LEFT JOIN account_move m ON (account_move_line.move_id = m.id)
            LEFT JOIN matching_in_futur_before_init mif ON (account_move_line.full_reconcile_id = mif.id)
       	WHERE
            m.state IN %s
            AND account_move_line.company_id = %s
            AND account_move_line.date < %s
            AND acc_type.include_initial_balance = TRUE
            AND account_move_line.journal_id IN %s
            AND account_move_line.account_id IN %s
            AND (%s OR account_move_line.partner_id IN %s)
            AND ((%s AND acc.compacted = TRUE) OR acc.type_third_parties = 'no' OR (account_move_line.full_reconcile_id IS NOT NULL AND mif.id IS NULL))
        GROUP BY
            group_by_key
        """
        account_type = True if self.type_ledger in ('general', 'open') else False

        params = [
            # matching_in_futur
            company.id,
            self.date_from,

            # init_account_table
            # SELECT
            self.report_id.id,
            self.env.uid,
            account_type,
            not(account_type),
            account_type,
            self.date_from,
            self.init_balance_history,
            self.init_balance_history,
            # WHERE
            ('posted',) if self.target_move == 'posted' else ('posted', 'draft',),
            company.id,
            self.date_from,
            tuple(self.journal_ids.ids) if self.journal_ids else (None,),
            tuple(self.account_ids.ids) if self.account_ids else (None,),
            True if self.type_ledger in ('general', 'open', 'journal') else False,
            tuple(self.partner_ids.ids) if self.partner_ids else (None,),
            self.compact_account
        ]

        self.env.cr.execute(query, tuple(params))

    def _sql_init_unreconcillied_table(self):
        # init_unreconcillied_table
        query = """INSERT INTO account_report_standard_ledger_line
            (report_id, create_uid, create_date, account_id, type, journal_id, partner_id, move_id,date, date_maturity, debit, credit, balance, full_reconcile_id, reconciled)

        WITH matching_in_futur_before_init (id) AS
        (
        SELECT DISTINCT
            afr.id
        FROM
            account_full_reconcile afr
        INNER JOIN account_move_line aml ON aml.full_reconcile_id=afr.id
        WHERE
            aml.company_id = %s
            AND aml.date >= %s
        ),

        matching_in_futur_after_date_to (id) AS
        (
        SELECT DISTINCT
            afr.id
        FROM
            account_full_reconcile afr
        INNER JOIN account_move_line aml ON aml.full_reconcile_id = afr.id
        WHERE
            aml.company_id = %s
            AND aml.date > %s
        )

        SELECT
            %s AS report_id,
            %s AS create_uid,
            NOW() AS create_date,
            account_move_line.account_id,
            '1_init_line' AS type,
            account_move_line.journal_id,
            account_move_line.partner_id,
            account_move_line.move_id,
            account_move_line.date,
            account_move_line.date_maturity,
            account_move_line.debit,
            account_move_line.credit,
            account_move_line.balance,
            account_move_line.full_reconcile_id,
            CASE WHEN account_move_line.full_reconcile_id is NOT NULL AND NOT mifad.id IS NOT NULL THEN TRUE ELSE FALSE END AS reconciled
        FROM
            account_move_line
            LEFT JOIN account_account acc ON (account_move_line.account_id = acc.id)
            LEFT JOIN account_account_type acc_type ON (acc.user_type_id = acc_type.id)
            LEFT JOIN account_move m ON (account_move_line.move_id = m.id)
            LEFT JOIN matching_in_futur_before_init mif ON (account_move_line.full_reconcile_id = mif.id)
            LEFT JOIN matching_in_futur_after_date_to mifad ON (account_move_line.full_reconcile_id = mifad.id)
       	WHERE
            m.state IN %s
            AND account_move_line.company_id = %s
            AND account_move_line.date < %s
            AND acc_type.include_initial_balance = TRUE
            AND account_move_line.journal_id IN %s
            AND account_move_line.account_id IN %s
            AND (%s OR account_move_line.partner_id IN %s)
            AND NOT (%s AND acc.compacted = TRUE)
            AND (%s OR NOT (account_move_line.full_reconcile_id is NOT NULL AND NOT mifad.id IS NOT NULL))
        	AND acc.type_third_parties IN ('supplier', 'customer') AND (account_move_line.full_reconcile_id IS NULL OR mif.id IS NOT NULL)
        ORDER BY
            account_move_line.date
        """

        params = [
            # matching_in_futur init
            self.company_id.id,
            self.date_from,

            # matching_in_futur date_to
            self.company_id.id,
            self.date_to,

            # init_unreconcillied_table
            # SELECT
            self.report_id.id,
            self.env.uid,
            # WHERE
            ('posted',) if self.target_move == 'posted' else ('posted', 'draft',),
            self.company_id.id,
            self.date_from,
            tuple(self.journal_ids.ids) if self.journal_ids else (None,),
            tuple(self.account_ids.ids) if self.account_ids else (None,),
            True if self.type_ledger in ('general', 'open', 'journal') else False,
            tuple(self.partner_ids.ids) if self.partner_ids else (None,),
            self.compact_account,
            self.reconciled,
        ]

        self.env.cr.execute(query, tuple(params))

    def _sql_lines(self):
        # lines_table
        query = """
        INSERT INTO account_report_standard_ledger_line
            (report_id, create_uid, create_date, account_id, type, journal_id, partner_id, move_id,date, date_maturity, debit, credit, balance, full_reconcile_id, reconciled)

        WITH matching_in_futur_after_date_to (id) AS
        (
        SELECT DISTINCT
            afr.id
        FROM
            account_full_reconcile afr
        INNER JOIN account_move_line aml ON aml.full_reconcile_id = afr.id
        WHERE
            aml.company_id = %s
            AND aml.date > %s
        )

        SELECT
            %s AS report_id,
            %s AS create_uid,
            NOW() AS create_date,
            account_move_line.account_id,
            '2_line' AS type,
            account_move_line.journal_id,
            account_move_line.partner_id,
            account_move_line.move_id,
            account_move_line.date,
            account_move_line.date_maturity,
            account_move_line.debit,
            account_move_line.credit,
            account_move_line.balance,
            account_move_line.full_reconcile_id,
            CASE WHEN account_move_line.full_reconcile_id is NOT NULL AND NOT mifad.id IS NOT NULL THEN TRUE ELSE FALSE END AS reconciled
        FROM
            account_move_line
            LEFT JOIN account_journal j ON (account_move_line.journal_id = j.id)
            LEFT JOIN account_account acc ON (account_move_line.account_id = acc.id)
            LEFT JOIN account_account_type acc_type ON (acc.user_type_id = acc_type.id)
            LEFT JOIN account_move m ON (account_move_line.move_id = m.id)
            LEFT JOIN matching_in_futur_after_date_to mifad ON (account_move_line.full_reconcile_id = mifad.id)
        WHERE
            m.state IN %s
            AND account_move_line.company_id = %s
            AND account_move_line.date >= %s
            AND account_move_line.date <= %s
            AND account_move_line.journal_id IN %s
            AND account_move_line.account_id IN %s
            AND (%s OR account_move_line.partner_id IN %s)
            AND NOT (%s AND acc.compacted = TRUE)
            AND (%s OR NOT (account_move_line.full_reconcile_id is NOT NULL AND NOT mifad.id IS NOT NULL))
        ORDER BY
            account_move_line.date
        """

        params = [
            # matching_in_futur date_to
            self.company_id.id,
            self.date_to,

            # lines_table
            self.report_id.id,
            self.env.uid,
            ('posted',) if self.target_move == 'posted' else ('posted', 'draft',),
            self.company_id.id,
            self.date_from,
            self.date_to,
            tuple(self.journal_ids.ids) if self.journal_ids else (None,),
            tuple(self.account_ids.ids) if self.account_ids else (None,),
            True if self.type_ledger in ('general', 'open', 'journal') else False,
            tuple(self.partner_ids.ids) if self.partner_ids else (None,),
            self.compact_account,
            self.reconciled,
        ]

        self.env.cr.execute(query, tuple(params))

    def _sql_lines_compacted(self):
        # lines_table
        query = """
        INSERT INTO account_report_standard_ledger_line
            (report_id, create_uid, create_date, account_id, type, date, debit, credit, balance)
        SELECT
            %s AS report_id,
            %s AS create_uid,
            NOW() AS create_date,
            MIN(account_move_line.account_id) AS account_id,
            '3_compact' AS type,
            %s AS date,
            COALESCE(SUM(account_move_line.debit), 0) AS debit,
            COALESCE(SUM(account_move_line.credit), 0) AS credit,
            COALESCE(SUM(account_move_line.balance), 0) AS balance
        FROM
            account_move_line
            LEFT JOIN account_journal j ON (account_move_line.journal_id = j.id)
            LEFT JOIN account_account acc ON (account_move_line.account_id = acc.id)
            LEFT JOIN account_account_type acc_type ON (acc.user_type_id = acc_type.id)
            LEFT JOIN account_move m ON (account_move_line.move_id = m.id)
        WHERE
            m.state IN %s
            AND account_move_line.company_id = %s
            AND account_move_line.date >= %s
            AND account_move_line.date <= %s
            AND account_move_line.journal_id IN %s
            AND account_move_line.account_id IN %s
            AND (%s AND acc.compacted = TRUE)
        GROUP BY
            account_move_line.account_id
        """

        params = [
            # SELECT
            self.report_id.id,
            self.env.uid,
            self.date_from,
            # WHERE
            ('posted',) if self.target_move == 'posted' else ('posted', 'draft',),
            self.company_id.id,
            self.date_from,
            self.date_to,
            tuple(self.journal_ids.ids) if self.journal_ids else (None,),
            tuple(self.account_ids.ids) if self.account_ids else (None,),
            self.compact_account,
        ]

        self.env.cr.execute(query, tuple(params))

    def _sql_account_total(self):
        query = """
        INSERT INTO account_report_standard_ledger_line
            (report_id, create_uid, create_date, account_id, type, date, debit, credit, balance, cumul_balance)
        SELECT
            %s AS report_id,
            %s AS create_uid,
            NOW() AS create_date,
            MIN(account_id),
            '4_total' AS type,
            %s AS date,
            COALESCE(SUM(debit), 0) AS debit,
            COALESCE(SUM(credit), 0) AS credit,
            COALESCE(SUM(balance), 0) AS balance,
            COALESCE(SUM(balance), 0) AS cumul_balance
        FROM
            account_report_standard_ledger_line
        WHERE
            report_id = %s
            AND account_id IS NOT NULL
        GROUP BY
            account_id
        """
        params = [
            # SELECT
            self.report_id.id,
            self.env.uid,
            self.date_from,
            # WHERE
            self.report_id.id,
        ]
        self.env.cr.execute(query, tuple(params))

        query = """WITH table_progress AS (
            SELECT
            	aml.id AS id,
            	SUM(aml.balance) OVER (PARTITION BY aml.account_id ORDER BY aml.account_id, aml.id) AS progress
            FROM
            	account_report_standard_ledger_line aml
            WHERE
            	report_id = %s
                AND type != '4_total')

            UPDATE account_report_standard_ledger_line ra
            SET
            	cumul_balance = table_progress.progress
            FROM
            	table_progress
            WHERE
            	ra.id = table_progress.id
            """
        params = [
            # WHERE
            self.report_id.id,
        ]
        self.env.cr.execute(query, tuple(params))

    def _sql_partner_total(self):
        query = """
        INSERT INTO account_report_standard_ledger_line
            (report_id, create_uid, create_date, partner_id, type, date, debit, credit, balance, cumul_balance)
        SELECT
            %s AS report_id,
            %s AS create_uid,
            NOW() AS create_date,
            MIN(partner_id),
            '4_total' AS type,
            %s AS date,
            COALESCE(SUM(debit), 0) AS debit,
            COALESCE(SUM(credit), 0) AS credit,
            COALESCE(SUM(balance), 0) AS balance,
            COALESCE(SUM(balance), 0) AS cumul_balance
        FROM
            account_report_standard_ledger_line
        WHERE
            report_id = %s
            AND partner_id IS NOT NULL
        GROUP BY
            partner_id
        """
        params = [
            self.report_id.id,
            self.env.uid,
            self.date_from,
            self.report_id.id,
        ]
        self.env.cr.execute(query, tuple(params))

        query = """WITH table_progress AS (
            SELECT
            	aml.id AS id,
            	SUM(aml.balance) OVER (PARTITION BY aml.partner_id ORDER BY aml.partner_id, aml.id) AS progress
            FROM
            	account_report_standard_ledger_line aml
            WHERE
            	report_id = %s
                AND type != '4_total')

            UPDATE account_report_standard_ledger_line ra
            SET
            	cumul_balance = table_progress.progress
            FROM
            	table_progress
            WHERE
            	ra.id = table_progress.id
            """
        params = [
            # WHERE
            self.report_id.id,
        ]
        self.env.cr.execute(query, tuple(params))

    def _search_account(self):
        type_ledger = self.type_ledger
        domain = [('deprecated', '=', False), ('company_id', '=', self.company_id.id)]
        if type_ledger in ('partner', 'aged',):
            result_selection = self.result_selection
            if result_selection == 'supplier':
                acc_type = ('supplier',)
            elif result_selection == 'customer':
                acc_type = ('customer',)
            else:
                acc_type = ('supplier', 'customer',)
            domain.append(('type_third_parties', 'in', acc_type))

        account_in_ex_clude = self.account_in_ex_clude.ids
        acc_methode = self.account_methode
        if account_in_ex_clude:
            if acc_methode == 'include':
                domain.append(('id', 'in', account_in_ex_clude))
            elif acc_methode == 'exclude':
                domain.append(('id', 'not in', account_in_ex_clude))
        return self.env['account.account'].search(domain)

    def _search_partner(self):
        if self.type_ledger in ('partner', 'aged'):
            if self.partner_select_ids:
                return self.partner_select_ids
            return self.env['res.partner'].search([])
        return False

    def _get_name_report(self):
        report_name = D_LEDGER[self.type_ledger]['name']
        if self.summary:
            report_name += _(' Balance')
        self.report_name = report_name
        self.name = report_name
