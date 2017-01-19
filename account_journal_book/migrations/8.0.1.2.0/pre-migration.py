# -*- encoding: utf-8 -*-


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        'ALTER TABLE account_move DROP CONSTRAINT '
        'account_move_number_in_book_uniq;')
