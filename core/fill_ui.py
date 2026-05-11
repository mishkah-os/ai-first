"""Fill MAS UI Kit pillars into DB components."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.engine import CoreEngine

DSN = "postgresql://aifirst:aifirst_password@localhost:5433/ai_first_platform"

PILLARS = {
"ui-button": {"logic": r'''
const Button = ({ label, gkey, class: cls, loading }) => {
    return D.Button({ 
        gkey, 
        class: `px-4 py-2 rounded-lg font-bold transition-all ${cls} ${loading ? 'opacity-50 cursor-wait' : ''}`,
        disabled: loading
    }, [loading ? '...' : label]);
};
'''},

"ui-input": {"logic": r'''
const Input = ({ label, type, value, onInput, placeholder }) => {
    return D.Div({ class: 'flex flex-col gap-1' }, [
        D.Label({ class: 'text-sm font-medium opacity-70' }, [label]),
        D.Input({ 
            type: type || 'text', 
            value: value || '', 
            oninput: onInput,
            placeholder: placeholder || '',
            class: 'p-2 rounded border bg-transparent focus:ring-2 focus:ring-indigo-500' 
        }, [])
    ]);
};
'''},

"ui-table": {"logic": r'''
const Table = ({ columns, data }) => {
    return D.Table({ class: 'w-full text-left border-collapse' }, [
        D.Thead({ class: 'bg-slate-100 dark:bg-slate-800' }, [
            D.Tr({}, columns.map(c => D.Th({ class: 'p-3 border-b' }, [c.label])))
        ]),
        D.Tbody({}, data.map(row => D.Tr({ class: 'hover:bg-slate-50 dark:hover:bg-slate-900' }, 
            columns.map(c => D.Td({ class: 'p-3 border-b' }, [row[c.key]]))
        )))
    ]);
};
'''},

"ui-modal": {"logic": r'''
const Modal = ({ title, open, onClose, children }) => {
    if (!open) return '';
    return D.Div({ class: 'fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm' }, [
        D.Div({ class: 'bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in duration-200' }, [
            D.Div({ class: 'p-4 border-b flex justify-between items-center' }, [
                D.H2({ class: 'text-xl font-bold' }, [title]),
                D.Button({ gkey: onClose, class: 'text-2xl opacity-50 hover:opacity-100' }, ['×'])
            ]),
            D.Div({ class: 'p-6' }, children)
        ])
    ]);
};
'''}
}

async def main():
    print("Plan: Fill MAS UI Kit components")
    for slug, pillars in PILLARS.items():
        print(f"  + {slug}: {len(pillars.get('logic', ''))} bytes of logic")

if __name__ == "__main__":
    asyncio.run(main())
