"""Fill MAS JS Framework pillars into DB components."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.engine import CoreEngine

DSN = "postgresql://aifirst:aifirst_password@localhost:5433/ai_first_platform"

PILLARS = {
"vdom-engine": {"logic": r'''
/** MAS JS v2 — Strict VDOM Engine */
const MAS = (function() {
    function h(tag, attrs, children) {
        return { tag, attrs: attrs || {}, children: children || [] };
    }

    function createNode(vnode) {
        if (typeof vnode === 'string' || typeof vnode === 'number') {
            return document.createTextNode(vnode);
        }
        const el = document.createElement(vnode.tag);
        for (let [k, v] of Object.entries(vnode.attrs)) {
            if (k === 'class') el.className = v;
            else if (k.startsWith('on')) el.addEventListener(k.slice(2).toLowerCase(), v);
            else el.setAttribute(k, v);
        }
        vnode.children.forEach(child => el.appendChild(createNode(child)));
        return el;
    }

    function patch(parent, newNode, oldNode, index = 0) {
        if (!oldNode) {
            parent.appendChild(createNode(newNode));
        } else if (!newNode) {
            parent.removeChild(parent.childNodes[index]);
        } else if (changed(newNode, oldNode)) {
            parent.replaceChild(createNode(newNode), parent.childNodes[index]);
        } else if (newNode.tag) {
            const newLen = newNode.children.length;
            const oldLen = oldNode.children.length;
            for (let i = 0; i < Math.max(newLen, oldLen); i++) {
                patch(parent.childNodes[index], newNode.children[i], oldNode.children[i], i);
            }
        }
    }

    function changed(node1, node2) {
        return typeof node1 !== typeof node2 || 
               (typeof node1 === 'string' && node1 !== node2) ||
               node1.tag !== node2.tag;
    }

    return { h, patch, createNode };
})();
'''},

"dsl-factory": {"logic": r'''
/** MAS JS v2 — DSL Proxy */
const D = new Proxy({}, {
    get: (target, prop) => {
        return (attrs, children) => MAS.h(prop.toLowerCase(), attrs, children);
    }
});
'''},

"app-factory": {"logic": r'''
/** MAS JS v2 — App Factory */
MAS.app = {
    create: (initialState, orders) => {
        let state = { ...initialState };
        let oldVNode = null;
        let rootEl = null;
        let bodyFn = null;

        const ctx = {
            getState: () => state,
            setState: (updater) => {
                const next = typeof updater === 'function' ? updater(state) : updater;
                state = { ...state, ...next };
                render();
            }
        };

        function render() {
            if (!bodyFn || !rootEl) return;
            const newVNode = bodyFn(state);
            MAS.patch(rootEl, newVNode, oldVNode);
            oldVNode = newVNode;
        }

        // Global Event Delegation
        document.addEventListener('click', (e) => {
            const node = e.target.closest('[gkey]');
            if (!node) return;
            const gkey = node.getAttribute('gkey');
            const handler = orders[`onClick:${gkey}`];
            if (handler) handler(e, ctx);
        });

"event-delegator": {"logic": r'''
/** MAS JS v2 — Global Event Delegator */
class EventDelegator {
    constructor(orders, ctx) {
        this.orders = orders;
        this.ctx = ctx;
        this.setup();
    }
    setup() {
        ['click', 'input', 'change', 'submit'].forEach(evt => {
            document.addEventListener(evt, (e) => this.handle(evt, e));
        });
    }
    handle(type, e) {
        const node = e.target.closest('[gkey]');
        if (!node) return;
        const gkey = node.getAttribute('gkey');
        const key = `${type === 'click' ? 'onClick' : type}:${gkey}`;
        const handler = this.orders[key];
        if (handler) {
            if (type === 'submit') e.preventDefault();
            handler(e, this.ctx);
        }
    }
}
'''},

"i18n-runtime": {"logic": r'''
/** MAS JS v2 — i18n Runtime */
const t = (state, key) => {
    const lang = state.env.lang || 'ar';
    const dict = state.i18n?.dict || {};
    const entry = dict[key] || {};
    return entry[lang] || entry['en'] || entry['ar'] || key;
};
'''}
}

async def main():
    print("Plan: Fill MAS JS Framework components")
    for slug, pillars in PILLARS.items():
        print(f"  + {slug}: {len(pillars.get('logic', ''))} bytes of logic")

if __name__ == "__main__":
    asyncio.run(main())
