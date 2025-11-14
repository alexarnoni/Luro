import sqlite3
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.core.validation import parse_money

DB = 'luro.db'

conn = sqlite3.connect(DB)
cur = conn.cursor()
try:
    # pick the test account and transaction created earlier
    cur.execute("SELECT id, balance FROM accounts WHERE id = 2")
    acc = cur.fetchone()
    if not acc:
        raise RuntimeError('Test account not found (id 2)')
    account_id, balance_before = acc
    print('Account before:', account_id, balance_before)

    # Update account using parse_money string
    new_balance_str = 'R$ 900,00'
    amount, warnings = parse_money(new_balance_str)
    print('Parsed new balance:', amount, warnings)
    cur.execute("UPDATE accounts SET balance = ? WHERE id = ?", (amount, account_id))
    conn.commit()
    cur.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,))
    print('Account after update:', cur.fetchone())

    # Edit transaction id 3: change from expense 123.45 to income 200.00
    cur.execute("SELECT id, account_id, amount, transaction_type FROM transactions WHERE id = 3")
    tx = cur.fetchone()
    if not tx:
        raise RuntimeError('Transaction id 3 not found')
    tx_id, tx_account_id, tx_amount, tx_type = tx
    print('Transaction before:', tx)

    # Revert old effect
    cur.execute("SELECT balance FROM accounts WHERE id = ?", (tx_account_id,))
    bal = cur.fetchone()[0]
    if tx_type == 'income':
        bal = bal - tx_amount
    else:
        bal = bal + tx_amount

    # Apply new effect
    new_amount_str = '200.00'
    new_amount, _ = parse_money(new_amount_str)
    new_type = 'income'
    if new_type == 'income':
        bal = bal + new_amount
    else:
        if bal < new_amount:
            raise RuntimeError('Insufficient funds')
        bal = bal - new_amount

    # Update account balance and transaction
    cur.execute("UPDATE accounts SET balance = ? WHERE id = ?", (bal, tx_account_id))
    cur.execute("UPDATE transactions SET amount = ?, transaction_type = ?, description = ? WHERE id = ?", (new_amount, new_type, 'Edited by auto test', tx_id))
    conn.commit()

    cur.execute("SELECT balance FROM accounts WHERE id = ?", (tx_account_id,))
    print('Account after txn edit:', cur.fetchone())
    cur.execute("SELECT id, amount, transaction_type, description FROM transactions WHERE id = ?", (tx_id,))
    print('Transaction after edit:', cur.fetchone())

except Exception as e:
    conn.rollback()
    print('Test failed:', e)
finally:
    cur.close()
    conn.close()
