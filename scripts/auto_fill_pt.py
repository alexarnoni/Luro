"""Auto-fill Portuguese (pt_BR) translations in messages.po using simple rules.

This is a convenience helper that makes a first-pass machine-like translation
for entries that have an empty msgstr. It uses a small phrase dictionary and
word substitutions. It's intentionally conservative: if no mapping is found it
keeps the original msgid so translations remain visible for manual review.

Run from project root: python scripts/auto_fill_pt.py
"""
from __future__ import annotations

from pathlib import Path
import polib

ROOT = Path(__file__).resolve().parents[1]
PO_PATH = ROOT / 'locale' / 'pt_BR' / 'LC_MESSAGES' / 'messages.po'

# Small phrase dictionary for common UI strings
PHRASE_MAP = {
    'Invalid balance format': 'Formato de saldo inválido',
    'Account updated': 'Conta atualizada',
    'Save failed': 'Falha ao salvar',
    'Unable to save account: ': 'Não foi possível salvar a conta: ',
    'Create account': 'Criar conta',
    'Add Account': 'Adicionar conta',
    'Add New Account': 'Adicionar nova conta',
    'Account Name': 'Nome da conta',
    'Account Type': 'Tipo de conta',
    'Initial Balance': 'Saldo inicial',
    'Accounts': 'Contas',
    'Edit': 'Editar',
    'Edit Account': 'Editar conta',
    'Name': 'Nome',
    'Balance': 'Saldo',
    'Cancel': 'Cancelar',
    'Create Account': 'Criar conta',
    'Register your first account': 'Registre sua primeira conta',
    'Organize your balances by connecting bank accounts or wallets you track manually.': 'Organize seus saldos conectando contas bancárias ou carteiras que você registra manualmente.',
    'Import CSV/OFX': 'Importar CSV/OFX',
    'Go to import': 'Ir para importação',
    'Português (Brasil)': 'Português (Brasil)',
    'English': 'Inglês',
    'Luro - Personal Finance Manager': 'Luro - Gerenciador Financeiro Pessoal',
    'Dashboard': 'Painel',
    'Transactions': 'Transações',
    'Goals': 'Metas',
    'Login': 'Entrar',
    'Logout': 'Sair',
    'Light mode': 'Modo claro',
    'Personal Finance Management': 'Gestão Financeira Pessoal',
    # additional common phrases
    'Welcome to Luro': 'Bem-vindo ao Luro',
    'Your personal finance management solution': 'Sua solução para gestão financeira pessoal',
    'Track your accounts, manage transactions, and achieve your financial goals.': 'Acompanhe suas contas, gerencie transações e alcance suas metas financeiras.',
    'Get Started': 'Começar',
    'Features': 'Recursos',
    'Account Management': 'Gerenciamento de contas',
    'Transaction Tracking': 'Rastreamento de transações',
    'Financial Goals': 'Metas financeiras',
    'Insights': 'Insights',
    'No transactions yet': 'Ainda não há transações',
    'Add transaction': 'Adicionar transação',
    'No goals yet. Create your first goal to start tracking your financial objectives!': 'Ainda não há metas. Crie sua primeira meta para começar a acompanhar seus objetivos financeiros!',
    'Select account': 'Selecionar conta',
    'Amount': 'Valor',
    'Description': 'Descrição',
    'Income': 'Receita',
    'Expense': 'Despesa',
    'Save': 'Salvar',
    'Processing...': 'Processando...',
    'Transaction updated': 'Transação atualizada',
    'Unable to save transaction: ': 'Não foi possível salvar a transação: '
}

# Word-level substitutions as fallback
WORD_MAP = {
    'Account': 'Conta',
    'Accounts': 'Contas',
    'Balance': 'Saldo',
    'Create': 'Criar',
    'Add': 'Adicionar',
    'Edit': 'Editar',
    'Save': 'Salvar',
    'Cancel': 'Cancelar',
    'Import': 'Importar',
    'Transactions': 'Transações',
    'Goals': 'Metas',
    'Dashboard': 'Painel',
    'Login': 'Entrar',
    'Logout': 'Sair',
}


def simple_translate(s: str) -> str:
    if not s:
        return s
    # exact phrase
    if s in PHRASE_MAP:
        return PHRASE_MAP[s]
    # punctuation-aware cleanup
    # attempt word-by-word replacement
    out = []
    for word in s.split(' '):
        core = word.strip(',:()."\'')
        lower = core
        repl = None
        if core in WORD_MAP:
            repl = WORD_MAP[core]
        elif core.capitalize() in WORD_MAP:
            repl = WORD_MAP[core.capitalize()]
        if repl:
            # preserve trailing punctuation
            suffix = word[len(core):]
            out.append(repl + suffix)
        else:
            out.append(word)
    return ' '.join(out)


def main():
    if not PO_PATH.exists():
        print('PO file not found:', PO_PATH)
        return
    po = polib.pofile(str(PO_PATH))
    changed = 0
    for entry in po:
        if entry.msgstr:
            continue
        if not entry.msgid or entry.msgid.strip() == '':
            continue
        tr = simple_translate(entry.msgid)
        if tr and tr != entry.msgid:
            entry.msgstr = tr
            changed += 1
    if changed:
        po.save()
    print(f'Auto-filled {changed} entries in {PO_PATH}')


if __name__ == '__main__':
    main()
