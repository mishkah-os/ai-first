# 🧬 Legacy DNA Vault — Complete Engineering Heritage

> هذا المجلد يحتوي على أهم الأكواد والوثائق من ثلاثة مشاريع: `ai`, `ai-auto`, `os`.
> **الفلسفة:** "اكتب الهيكل مرة واحدة — دعه يولّد كل شيء."

---

## 📁 الهيكل الكامل

```
legacy_dna/
├── schema_driven/              ← 🔥 قلب الفلسفة: Schema يولّد كل شيء
│   ├── mas-schema.js           ← محرك Schema → SQL → Validation (582 سطر)
│   ├── mas-rest.js             ← عميل REST ذكي مع Cache + Queue + Sync (1435 سطر)
│   ├── UniversalComp.js        ← مكونات CRUD ديناميكية من Schema (403 سطر)
│   └── erd.html                ← متصفح ERD مرئي يقرأ Schema تلقائياً
│
├── frontend_v3/                ← نواة الفرونت إند
│   ├── mas.core.js             ← 🔥 محرك VDOM + DSL + Event Delegation (78KB)
│   ├── mas-store-v3.js         ← إدارة الحالة + Delta Sync + Outbox (45KB)
│   ├── mas-ui.js               ← 🔥 مكتبة المكونات + Design Tokens (128KB)
│   ├── mas-utils.js            ← أدوات: twcss, storage, network (159KB)
│   ├── hawaa_app.js            ← تطبيق MAS كامل (363 سطر)
│   └── hawaa_db.js             ← طبقة البيانات المحلية (256 سطر)
│
├── quantum_orm/                ← محرك ORM ثنائي اللغة
│   ├── postgres.js             ← ORM ديناميكي JS (1164 سطر)
│   └── main.cpp                ← ORM عالي الأداء C++ (1899 سطر)
│
├── ai_track3/                  ← محرك التعديل الجراحي
│   ├── track3_engine.py        ← المحرك الرئيسي (1603 سطر)
│   ├── surgical_skeletonizer.py ← محلل الكود Tree-sitter (1763 سطر)
│   └── test_track3.py          ← اختبارات (528 سطر)
│
├── backend_runtime/            ← الباك إند
│   ├── server.runtime.js       ← الخادم الرئيسي (51KB)
│   ├── crud-api.js             ← CRUD ديناميكي (53KB)
│   ├── pubsub.js               ← نظام البث (37KB)
│   ├── queryBuilder.js         ← بناء استعلامات آمن (17KB)
│   ├── eventStore.js           ← سجل الأحداث (15KB)
│   └── delta-engine.js         ← محرك التحديثات اللحظية (5KB)
│
└── docs/                       ← الوثائق المرجعية
    ├── MAS_FRAMEWORK.md        ← وثيقة MAS JS Framework الكاملة
    └── SCHEMA_DRIVEN.md        ← وثيقة فلسفة Schema-Driven
```

---

## 🔥 الفلسفة الأساسية: Schema-Driven Architecture

### ما هي؟
في نظام MAS، ملف الـ Schema ليس مجرد توثيق — **هو كود قابل للتنفيذ**.
من ملف JSON واحد، يتم توليد:
1. **جداول SQL** — بأمر واحد `generateSQL()`
2. **Validation** — التحقق من صحة البيانات في الفرونت والباك
3. **CRUD APIs** — واجهات REST تلقائية
4. **ERD** — مخططات بصرية تلقائية
5. **UI Components** — واجهات المستخدم تتكيف مع الـ Schema

### المشاكل:
- ❌ الـ Schema مبعثر بين JSON وأكواد JS
- ❌ لا يوجد versioning أو migration تلقائي

### ما نحله في النظام الجديد:
- ✅ الـ Schema يعيش في PostgreSQL كمصدر وحيد
- ✅ الـ Compiler يولّد كل شيء من قاعدة البيانات

---

## 🔬 تحليل تفصيلي

### `schema_driven/mas-schema.js` — محرك الـ Schema
**المصدر:** `os/static/lib2/mas-schema.js` (582 سطر)

**العبقرية:**
- `TYPE_CONFIG`: خريطة كاملة لـ 18 نوع بيانات (uuid, json, boolean, datetime...)
- `FieldDefinition`: يحوّل تعريف JSON إلى `columnSQL()` جاهز
- `TableDefinition.toSQL()`: يولّد `CREATE TABLE` كاملاً مع Foreign Keys
- `SchemaRegistry.topologicallySorted()`: يرتب الجداول بحسب التبعيات (DAG)
- `SchemaRegistry.generateSQL()`: يولّد قاعدة بيانات كاملة بأمر واحد

**المشاكل:**
- ❌ يعمل فقط في المتصفح (IIFE)
- ❌ لا يدعم ALTER TABLE أو migrations

---

### `schema_driven/mas-rest.js` — عميل REST ذكي
**المصدر:** `os/static/lib2/mas-rest.js` (1435 سطر)

**العبقرية:**
- **Stale-While-Revalidate Cache**: يعرض البيانات القديمة فوراً ثم يحدّث في الخلفية
- **Offline Queue**: يحفظ الطلبات في IndexedDB عند فقدان الاتصال ويعيد إرسالها
- **Exponential Backoff**: إعادة المحاولة بتأخير متصاعد
- **Sync Engine**: مزامنة كاملة للجداول مع ETag support
- **Multi-tenant**: يدعم Branch + Module isolation

**المشاكل:**
- ❌ Sync و Cache و Queue كلها في ملف واحد 1435 سطر
- ❌ مرتبط بـ IndexedDB adapter خارجي

---

### `schema_driven/UniversalComp.js` — مكونات Schema-Driven
**المصدر:** `os/static/projects/clinic/UniversalComp.js` (403 سطر)

**العبقرية:**
- **أي جدول → واجهة كاملة**: `Sidebar` + `Table` + `FormInput` تلقائياً
- **Foreign Key Resolution**: يحل العلاقات ويعرض Display Names
- **i18n Display**: `resolveDisplayName()` يبحث في 5 طبقات للعثور على الترجمة
- **Pure DSL**: كل شيء مبني بـ `D.Div`, `D.Button`, `D.Table`

---

### `frontend_v3/mas.core.js` — نواة VDOM
**المصدر:** `os/static/lib2/mas.core.js` (78KB)

**العبقرية:**
- **DSL Factory**: `D.Div()`, `D.Button()`, `D.Table()` — لكل عنصر HTML
- **Surgical DOM Patch**: يقارن VDOM ويطبّق فقط التغييرات
- **Single Delegated Listener**: مستمع واحد في الجذر يوزّع الأحداث عبر `gkey`
- **App Factory**: `app.create(db, orders).mount('#app')` — سطر واحد لتشغيل تطبيق

**المعمارية:**
```
State (db)  →  body(db)  →  VDOM  →  surgical DOM patch
     ↑                                        |
     └──────────── orders (event handlers) ───┘
```

**المشاكل:**
- ❌ 78KB ملف واحد
- ❌ يخلط Routing مع Rendering

---

### `frontend_v3/mas-ui.js` — مكتبة المكونات + Design System
**المصدر:** `os/static/lib2/mas-ui.js` (128KB, 2721 سطر)

**العبقرية:**
- **Design Tokens**: نظام كامل من المتغيرات CSS (`--primary`, `--card`, `--border`...)
- **130+ Token**: btn, card, modal, toolbar, tabs, drawer, badge, toast, numpad...
- **Chart.js Bridge**: `UI.Chart.Line()`, `UI.Chart.Bar()` — رسوم بيانية بسطر واحد
- **Theme-Aware**: كل المكونات تتكيف مع Light/Dark تلقائياً
- **CSS Variable Resolution**: يحل `var(--color)` في Chart.js dynamically

**المشاكل:**
- ❌ 128KB — ضخم جداً
- ❌ يعتمد على TailwindCSS CDN

---

### `frontend_v3/mas-utils.js` — أدوات النظام
**المصدر:** `os/static/lib2/mas-utils.js` (159KB)

**العبقرية:**
- **twcss**: محرك CSS-in-JS خفيف
- **JSON utilities**: `stableStringify`, `parseSafe`, `deepMerge`, `clone`
- **Data helpers**: تحويلات التواريخ، الأرقام، العملات
- **Network**: fetch wrappers مع retry logic
- **Storage**: localStorage/sessionStorage مع fallbacks

---

### `quantum_orm/` — ORM ثنائي اللغة
**المصدر:** `ai-auto/quantum/` + `ai-auto/quantum-cpp/`

**العبقرية:**
- **نفس المنطق بلغتين**: JS (1164 سطر) + C++ (1899 سطر)
- **Schema-to-CRUD**: يقرأ JSON Schema ويولّد Read/Save/Delete/Routine
- **Type Coercion**: `parseBooleanLike`, `parseIntegerLike`, `unwrapInputValue`
- **Crockford Base32 IDs**: توليد مفاتيح عامة فريدة

---

### `ai_track3/` — محرك التعديل الجراحي
**المصدر:** `ai/`

**العبقرية:**
- **Blinded State**: يخفي جسم الكود ويكشف فقط التوقيعات
- **Array Protocol**: `["r", "3:5", "new code"]`
- **Tree-sitter**: تحليل AST دقيق لـ 8 لغات
- **Stable Block IDs**: هوية ثابتة لكل بلوك حتى بعد التعديل

---

### `backend_runtime/` — الباك إند
**المصدر:** `os/src/` + `os/src/runtime/`

**العبقرية:**
- **crud-api.js**: واجهة CRUD ديناميكية من Schema (53KB)
- **pubsub.js**: اشتراكات على مستوى الجدول مع Scope Filtering (37KB)
- **delta-engine.js**: Cursor-Based Sync — يرسل فقط التحديثات المفقودة
- **queryBuilder.js**: بناء SQL آمن مع Table/Column whitelisting
- **eventStore.js**: سجل أحداث append-only

---

## 📖 الوثائق المرجعية

### `docs/MAS_FRAMEWORK.md`
وثيقة MAS JS Framework الكاملة — تشرح:
- **7 أركان معمارية**: Single State, Constrained DSL, Event Delegation...
- **Module System**: كيف تقسم تطبيق كبير إلى features
- **Governance Layer**: Guardian + Auditor + DevTools

### `docs/SCHEMA_DRIVEN.md`
وثيقة فلسفة Schema-Driven — تشرح:
- لماذا نبدأ دائماً بملف Schema + Seeds
- كيف يولّد المحرك SQL + ERD + Validation تلقائياً
- سير العمل من Frontend إلى Backend

---

## 🎯 خريطة الإرث → النظام الجديد

| المجال | القديم (الملفات) | الجديد (قاعدة البيانات) |
|--------|-----------------|----------------------|
| **Schema** | JSON files → `mas-schema.js` | `schema_registry` table in PG |
| **VDOM** | `mas.core.js` 78KB | مكونات ذرية في `code_blocks` |
| **UI Kit** | `mas-ui.js` 128KB | Design tokens في `style_blocks` |
| **State** | `mas-store-v3.js` 45KB | `mas-data.js` مبسط |
| **REST** | `mas-rest.js` 1435 سطر | Python Gateway تلقائي |
| **ORM** | `postgres.js` + `main.cpp` | C++ Core ذري |
| **CRUD** | `crud-api.js` 53KB | Schema → API تلقائي |
| **Sync** | `delta-engine.js` + `pubsub.js` | PG NOTIFY + WS Relay |
| **AI** | `track3_engine.py` 1603 سطر | QDML Protocol |
| **ERD** | `erd.html` (AntV X6) | مدمج في النواة |

---

> **"اكتب الهيكل مرة واحدة، دعه يولد واجهات العرض، ويدير التحقق، ويرسم مخططاتك، ويبني خوادمك."**
>
> هذه ليست مجرد فلسفة — هذا هو الكود الذي أثبت نجاحها في الإنتاج.
