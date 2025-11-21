import sqlite3
from datetime import datetime

DB = 'luro.db'
TEST_USER_EMAIL = 'test_auto_user@example.com'

conn = sqlite3.connect(DB)
cur = conn.cursor()
try:
    # Start transaction
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    # Create test user
    cur.execute("INSERT INTO users (email, name, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (TEST_USER_EMAIL, 'Auto Test', 1, now, now))
    user_id = cur.lastrowid
    print('Created user id', user_id)

    # Create test account with balance 1000.00
    cur.execute("INSERT INTO accounts (user_id, name, account_type, balance, currency, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, 'Auto Test Account', 'checking', 1000.0, 'USD', now, now))
    account_id = cur.lastrowid
    print('Created account id', account_id)

    # Create test goal with target 500.00
    cur.execute("INSERT INTO goals (user_id, name, description, target_amount, current_amount, is_completed, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, 'Auto Test Goal', 'Goal for automated test', 500.0, 0.0, 0, now, now))
    goal_id = cur.lastrowid
    print('Created goal id', goal_id)

    # Contribution amount
    amount = 123.45

    # Check account balance
    cur.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,))
    row = cur.fetchone()
    if not row:
        raise RuntimeError('Account not found')
    balance_before = row[0]
    print('Account balance before:', balance_before)

    if balance_before < amount:
        raise RuntimeError('Insufficient funds to perform test contribution')

    # Insert transaction (expense)
    cur.execute(
        "INSERT INTO transactions (account_id, amount, transaction_type, category, description, transaction_date, created_at, updated_at, goal_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (account_id, amount, 'expense', 'goal_contribution', f'Automated contribution to goal {goal_id}', now, now, now, goal_id)
    )
    tx_id = cur.lastrowid
    print('Inserted transaction id', tx_id)

    # Update account balance
    new_balance = balance_before - amount
    cur.execute("UPDATE accounts SET balance = ?, updated_at = ? WHERE id = ?", (new_balance, now, account_id))
    print('Account balance after:', new_balance)

    # Update goal current_amount
    cur.execute("SELECT current_amount, target_amount FROM goals WHERE id = ?", (goal_id,))
    g_row = cur.fetchone()
    current_amount = g_row[0]
    target_amount = g_row[1]
    new_current = (current_amount or 0.0) + amount
    is_completed = 1 if (target_amount and new_current >= target_amount) else 0
    cur.execute("UPDATE goals SET current_amount = ?, is_completed = ?, updated_at = ? WHERE id = ?", (new_current, is_completed, now, goal_id))
    print('Goal current_amount after:', new_current, 'is_completed:', is_completed)

    # Commit transaction
    conn.commit()

    # Verify inserted row
    cur.execute("SELECT id, account_id, amount, transaction_type, goal_id FROM transactions WHERE id = ?", (tx_id,))
    print('Transaction row:', cur.fetchone())
    cur.execute("SELECT id, balance FROM accounts WHERE id = ?", (account_id,))
    print('Account row:', cur.fetchone())
    cur.execute("SELECT id, current_amount, target_amount, is_completed FROM goals WHERE id = ?", (goal_id,))
    print('Goal row:', cur.fetchone())

except Exception as e:
    conn.rollback()
    print('Test failed:', e)
finally:
    cur.close()
    conn.close()
