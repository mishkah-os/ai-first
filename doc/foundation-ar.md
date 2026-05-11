# AI-First: المواصفات المعمارية الشاملة

> **المشروع**: ai-first  
> **المراجعة**: 4 — 2026-05-09  
> **الحالة**: المخطط المعماري النهائي  
> **النطاق**: نظام متكامل (الواجهة الأمامية + الواجهة الخلفية + عمليات التطوير DevOps + أدوات الذكاء الاصطناعي)

---

## 1. الفرضية الأساسية

تعمل جميع أنظمة البرمجة الحالية — سواء كانت أدوات للمطورين أو مساعدي الذكاء الاصطناعي — على **الملفات**. مصدر الحقيقة (Source of Truth) هو نظام الملفات، وتقوم كل أداة بهندسة عكسية للهيكل من خلال النصوص.

نظام **AI-First** (الذكاء الاصطناعي أولاً) يلغي الملفات تماماً من عملية التطوير. مصدر الحقيقة هنا هو **قاعدة بيانات علائقية** (Relational Database). يتم تخزين الكود والاستعلام عنه وتعديله كسجلات مهيكلة. يتم إنشاء الملفات عند الطلب بواسطة مترجم (Compiler) — فهي مجرد مخرجات بناء (Build Artifacts)، ولا يتم تعديلها يدوياً على الإطلاق.

تحدد هذه الوثيقة **النظام المتكامل**: تصيير الواجهة الأمامية (Frontend Rendering)، محرك الربط بين الكائنات وقواعد البيانات (Backend ORM)، المزامنة في الوقت الفعلي، الأمان، النشر، وبيئة تطوير الذكاء الاصطناعي التي تبني كل شيء انطلاقاً من قاعدة بيانات تعتمد على المخطط (Schema-first).

### ما نحتفظ به من الأنظمة السابقة

| النظام | ما نجح | ما فشل | ما يأخذه AI-First |
|--------|------------|-------------|-------------------|
| **MAS Store v3** | مزامنة الاختلافات عبر WebSocket (WS delta sync)، تخزين مؤقت عبر IndexedDB، طابور الصادر، إعادة التشغيل بناءً على المؤشر (Cursor) | عدم وجود سجل أحداث (change-log) لعمليات الحذف، قواعد أمان ضعيفة، عدم فصل البيانات الحية (live) عن العميقة (deep) | بروتوكول مزامنة الاختلافات، تتبع المؤشر، طابور الصادر للعمل دون اتصال بالإنترنت |
| **OS Server Runtime** | محرك المخططات (Schema engine)، التخزين الهجين (Hybrid store)، واجهة برمجة التطبيقات CRUD، مدير النشر والاشتراك (Pubsub manager)، معالج أحداث الوحدات، عزل الفروع/الوحدات | محرك ORM أضعف من Quantum، تخزين يعتمد على الملفات (SQLite/JSON)، تقسيم الصفحات (paging) غير دقيق | نموذج عزل الفروع/الوحدات، معمارية Pubsub، محمل سياسات الأمان |
| **Quantum (ai-auto)** | محرك ORM مدفوع بالمخططات لـ PostgreSQL، ميزات ذكية (`smart_features`) لكل جدول، محرك الشجرة (tree engine)، نظام الترجمة، محرك أساسي بلغة C++ | نظام منفصل عن OS runtime (غير موحد)، قاعدتي كود برمجيتين تحتاجان للصيانة | نموذج عقد المخطط (Schema contract)، الميزات الذكية، محرك C++ الأساسي، ملف تعريف `quantum_raw_v1` |
| **Ant-Swarm** | تنسيق وتوجيه لعدة مزودي ذكاء اصطناعي (Multi-provider orchestration)، اختبار متصفح Playwright، تعديلات Track3 الجراحية الدقيقة | إعداد معقد، ملفات كثيرة، غير مدفوع بالمخططات | كتالوج مزودي الذكاء الاصطناعي، تكامل Playwright، واجهة نصية لواجهة برمجة التطبيقات (API text interface) |

### المشكلتان الأساسيتان اللتان نحلهما

1. **عدم وجود مصدر موحد للحقيقة.** يستخدم نظام OS ملفات SQLite/JSON للبيانات الحية. بينما يستخدم Quantum قاعدة PostgreSQL للبيانات العميقة. يقوم MAS Store v3 بالمزامنة عبر WebSocket ولكنه لا يستطيع نشر عمليات الحذف (propagate deletes). يتم تعريف المخطط في الواجهة الأمامية (كائن `db`) والمخطط في الواجهة الخلفية (جداول SQL) بشكل مستقل وينحرفان عن بعضهما. **يجعل نظام AI-First مخطط قاعدة البيانات هو المصدر الوحيد للحقيقة لكل من الواجهتين الأمامية والخلفية.**

2. **عدم وجود بروتوكول مزامنة عميق.** عندما يتم حذف سجل في الواجهة الخلفية، لا يوجد ما يخبر الواجهة الأمامية "احذف هذا من IndexedDB". تتعامل أحداث `server:patch` الحالية مع عمليات التحديث/الإدراج (upserts) فقط بشكل موثوق. **ينفذ نظام AI-First سجل تغييرات (change-log) كامل مع علامات الحذف (tombstones)، وإعادة التشغيل المتتبعة بالمؤشر (cursor-tracked replay)، ونشر ثنائي الاتجاه لعمليات الحذف.**

---

## 2. مبادئ غير قابلة للتفاوض

| # | المبدأ | التأثير |
|---|-----------|-------------|
| 1 | **المخطط أولاً، كل شيء مشتق منه** | يحدد مستند JSON schema واحد جداول PostgreSQL ومخازن IndexedDB في الواجهة الأمامية وواجهات برمجة التطبيقات API وقواعد الأمان. لا يوجد شيء دون تعريف في المخطط. |
| 2 | **مشروع واحد = قاعدة بيانات واحدة** | قاعدة بيانات PostgreSQL لكل مشروع. دعم الإيجار المتعدد (Multi-tenancy) وتعدد الإصدارات اختياري بداخلها. |
| 3 | **استرجاع شامل للمكون** | يعيد استعلام واحد بمعرف ID جميع الركائز (pillars): المخطط، القالب (template)، المنطق (logic)، النمط (style) بالإضافة إلى مفاتيح الترجمة i18n والمكونات الفرعية. |
| 4 | **بروتوكول مزامنة كامل** | كل تعديل (إنشاء، تحديث، حذف) يولد حدثاً في سجل التغييرات مع مؤشرات (cursors). يعيد العملاء التشغيل من آخر مؤشر لهم عند إعادة الاتصال. تنتشر عمليات الحذف كعلامات حذف (tombstones). |
| 5 | **قواعد الأمان في المخطط** | يحدد كل جدول `access_rules` (قواعد الوصول) في مخططه: من يمكنه القراءة، الكتابة، الحذف، وما هي الحقول السرية، وما هي الحقول المقفلة. تفرض بيئة التشغيل هذه القواعد، وليس كود التطبيق. |
| 6 | **محرك أساسي بلغة C++** | يعمل محرك ORM العميق (منشئ الاستعلامات، عمليات الشجرة، التحقق من المخطط، توليد DDL) كملف تنفيذي مجمع بلغة C++. تعمل Python و JS كأغلفة (wrappers) فقط. أقصى أداء مع أقل كود. |
| 7 | **لا توجد ملفات ثابتة** | لا توجد ملفات تكوين، ولا كود أساسي متكرر (boilerplate). يبدأ المشروع كمخطط قاعدة بيانات. يولد النظام كل شيء آخر: `Dockerfile`، `docker-compose.yml`، `tailwind.config.js`، ملفات التبعيات، وبرامج الترحيل (migration scripts). |
| 8 | **أكواد مصغرة محجوبة (Blinded Mini Code)** | يرى الذكاء الاصطناعي الهياكل التنظيمية (skeletons) أولاً. يتم الكشف عن الأجسام الكاملة بناءً على طلب صريح. تتم فهرسة الوظائف المشتركة والأدوات المساعدة (utils) والمتغيرات العامة وتضمينها في الهيكل. |
| 9 | **مفاتيح الترجمة i18n أولاً** | تستخدم جميع السلاسل النصية المواجهة للمستخدم `t('key')`. المفاتيح عامة على مستوى المشروع. يتحقق المترجم (compiler) من كل إشارة لمفتاح. |
| 10 | **Tailwind + متغيرات CSS** | تخصيص المظهر (Theming) يتم عبر خصائص CSS المخصصة. Tailwind هي طبقة الأدوات المساعدة. يمنع استخدام قيم الألوان الخام في القوالب. |

---

## 3. نموذج البيانات الموحد

### 3.1 مستند المخطط (المصدر الوحيد للحقيقة)

هذا هو المستند الرئيسي. يتم اشتقاق كل شيء — جداول قاعدة البيانات، مسارات API، مخازن الواجهة الأمامية، وقواعد الأمان — من مستند JSON schema واحد.

```json
{
  "meta": {
    "project": "my-erp",
    "version": "1.0.0",
    "contracts": {
      "quantum_raw_v1": {
        "fingerprint": "quantum-raw-v1",
        "transport_profile": "cpp-core"
      }
    }
  },
  "schema": {
    "tables": [
      {
        "name": "invoices",
        "sqlName": "invoices",
        "fields": [
          { "name": "id", "columnName": "id", "type": "uuid", "primaryKey": true },
          { "name": "tenant_id", "columnName": "tenant_id", "type": "uuid", "references": { "table": "tenants", "column": "id" } },
          { "name": "customer_id", "columnName": "customer_id", "type": "uuid", "references": { "table": "customers", "column": "id" } },
          { "name": "total", "columnName": "total", "type": "decimal", "default": 0 },
          { "name": "status", "columnName": "status", "type": "text", "default": "draft" },
          { "name": "created_at", "columnName": "created_at", "type": "timestamptz" },
          { "name": "updated_at", "columnName": "updated_at", "type": "timestamptz" }
        ],
        "smart_features": {
          "display_field": "doc_no",
          "search_fields": ["doc_no", "status"],
          "is_translatable": false,
          "tree": null
        },
        "storage": {
          "live": true,
          "deep_paging": true,
          "window_days": 30,
          "top_n": 50
        },
        "access_rules": {
          "read": { "scope": "tenant", "field": "tenant_id" },
          "write": { "roles": ["admin", "accountant"] },
          "delete": { "roles": ["admin"] },
          "secret_fields": [],
          "locked": false
        }
      }
    ]
  }
}
```

### 3.2 ما يولده المخطط

```
مستند المخطط (JSON)
  ├── كود إنشاء الجداول لـ PostgreSQL (DDL: CREATE TABLE, indexes, constraints)
  ├── مخازن IndexedDB للواجهة الأمامية (keyPath, indexes)
  ├── مسارات واجهة برمجة التطبيقات (/api/v1/{table})
  ├── البرمجيات الوسيطة للأمان (تطبيق access_rules)
  ├── عمليات CRUD (مولدة تلقائياً)
  ├── اشتراكات WS الحية (للجداول storage.live)
  ├── استعلامات تقسيم الصفحات العميقة (deep paging)
  ├── جداول ترجمة i18n ({table}_lang)
  └── عمليات الشجرة (للجداول التي تم تفعيل smart_features.tree فيها)
```

### 3.3 نموذج المكونات (الواجهة الأمامية)

يتم تخزين كل مكون واجهة مستخدم (UI component) في قاعدة البيانات مع دعم الاسترجاع الشامل:

```sql
-- MODULE: حد الميزة (Feature boundary)
CREATE TABLE module (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,
    sort_order  INT DEFAULT 0,
    meta        JSONB DEFAULT '{}'
);

-- COMPONENT: الوحدة الذرية القابلة للعنونة
CREATE TABLE component (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id   UUID NOT NULL REFERENCES module(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'organism'
                CHECK (kind IN ('screen','organism','molecule','atom','kit')),
    lang        TEXT NOT NULL DEFAULT 'js',
    meta        JSONB DEFAULT '{}',
    UNIQUE(module_id, slug)
);

-- COMPONENT_CHILD: التكوين (Composition)
CREATE TABLE component_child (
    parent_id   UUID NOT NULL REFERENCES component(id) ON DELETE CASCADE,
    child_id    UUID NOT NULL REFERENCES component(id) ON DELETE CASCADE,
    slot        TEXT NOT NULL DEFAULT 'body',
    sort_order  INT DEFAULT 0,
    PRIMARY KEY (parent_id, child_id, slot)
);

-- PILLAR: الاهتمامات الأربعة المنفصلة (الركائز)
CREATE TABLE pillar (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component_id    UUID NOT NULL REFERENCES component(id) ON DELETE CASCADE,
    type            TEXT NOT NULL CHECK (type IN ('schema','template','logic','style')),
    body            TEXT NOT NULL DEFAULT '',
    body_hash       TEXT GENERATED ALWAYS AS (md5(body)) STORED,
    line_count      INT GENERATED ALWAYS AS (
                        array_length(string_to_array(body, E'\n'), 1)
                    ) STORED,
    version         INT NOT NULL DEFAULT 1,
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(component_id, type)
);

-- الوظائف المشتركة والأدوات المساعدة (SHARED FUNCTIONS & UTILS)
CREATE TABLE shared_function (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id   UUID REFERENCES module(id) ON DELETE SET NULL,  -- NULL = عام على مستوى المشروع
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'util', -- 'util', 'helper', 'formatter', 'validator'
    lang        TEXT NOT NULL DEFAULT 'js',
    body        TEXT NOT NULL DEFAULT '',
    signature   TEXT,  -- مثال: '(items: Array, key: string) => object'
    description TEXT,
    UNIQUE(slug)
);

-- المتغيرات والثوابت العامة (GLOBAL VARIABLES & CONSTANTS)
CREATE TABLE global_var (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id   UUID REFERENCES module(id) ON DELETE SET NULL,
    name        TEXT NOT NULL,
    value_type  TEXT NOT NULL DEFAULT 'string', -- 'string', 'number', 'object', 'array'
    value       TEXT NOT NULL,
    scope       TEXT NOT NULL DEFAULT 'project', -- 'project', 'module', 'screen'
    UNIQUE(name)
);

-- i18n: سجل المفاتيح العام للمشروع
CREATE TABLE i18n_key (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace   TEXT NOT NULL DEFAULT 'global',
    key_path    TEXT NOT NULL,
    meta        JSONB DEFAULT '{}',
    UNIQUE(namespace, key_path)
);

CREATE TABLE i18n_value (
    key_id      UUID NOT NULL REFERENCES i18n_key(id) ON DELETE CASCADE,
    lang_code   TEXT NOT NULL,
    value       TEXT NOT NULL,
    PRIMARY KEY (key_id, lang_code)
);

-- رموز التصميم (DESIGN TOKENS)
CREATE TABLE design_token (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category    TEXT NOT NULL,
    name        TEXT NOT NULL,
    value       TEXT NOT NULL,
    theme       TEXT NOT NULL DEFAULT 'default',
    UNIQUE(category, name, theme)
);

-- سجل التعديلات (MUTATION LOG)
CREATE TABLE mutation_log (
    id          BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id   UUID NOT NULL,
    action      TEXT NOT NULL,
    before_hash TEXT,
    after_hash  TEXT,
    diff        JSONB,
    actor       TEXT DEFAULT 'ai',
    model       TEXT,
    ts          TIMESTAMPTZ DEFAULT now()
);

-- سجل التغييرات (CHANGE LOG) (لبروتوكول المزامنة)
CREATE TABLE change_log (
    id          BIGSERIAL PRIMARY KEY,
    table_name  TEXT NOT NULL,
    record_id   TEXT NOT NULL,
    action      TEXT NOT NULL CHECK (action IN ('insert', 'update', 'delete')),
    delta       JSONB,
    cursor_seq  BIGINT NOT NULL,
    tombstone   BOOLEAN DEFAULT false,
    ts          TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_changelog_cursor ON change_log(cursor_seq);
CREATE INDEX idx_changelog_table ON change_log(table_name, cursor_seq);
```

---

## 4. معمارية الواجهة الخلفية (Backend Architecture)

### 4.1 المحرك الأساسي بلغة C++

يعمل محرك ORM العميق كملف تنفيذي مجمع بلغة C++ (موروث من `quantum-cpp` في Quantum). ويتولى:

- **توليد DDL**: من JSON المخطط → جمل `CREATE TABLE`
- **منشئ الاستعلامات**: SQL ذو معلمات (Parameterized SQL) مع الصلات (joins)، الفلاتر، تقسيم الصفحات، واجتياز الشجرة
- **التحقق من المخطط**: التحقق من السجلات مقابل عقد المخطط (schema contract) قبل الكتابة
- **عمليات الشجرة**: البيانات الهرمية (دليل الحسابات، الفئات) مع اجتياز `parent_id`
- **محرك الترحيل (Migration Engine)**: مقارنة نسختين من المخطط → توليد جمل `ALTER TABLE`

يكشف المحرك الثنائي C++ عن **بروتوكول JSON عبر stdio**:
```
→ {"op":"query","table":"invoices","filters":{"status":"draft"},"page":1,"limit":50}
← {"rows":[...],"total":142,"page":1,"pages":3}

→ {"op":"ddl","schema":{...}}
← {"sql":"CREATE TABLE invoices (...);","migrations":["ALTER TABLE ..."]}

→ {"op":"validate","table":"invoices","record":{...}}
← {"valid":true,"errors":[]}
```

### 4.2 خادم Python (FastAPI)

خادم واجهة برمجة التطبيقات (API server) هو طبقة Python خفيفة فوق محرك C++ الأساسي:

```
خادم FastAPI
  ├── /api/v1/{table}           ← العمليات الأساسية CRUD (تُفوض لمحرك C++)
  ├── /api/v1/{table}/{id}      ← سجل مفرد
  ├── /api/v1/schema            ← فحص المخطط (Schema introspection)
  ├── /qdml/describe            ← بروتوكول الذكاء الاصطناعي
  ├── /qdml/reveal              ← بروتوكول الذكاء الاصطناعي
  ├── /qdml/mutate              ← بروتوكول الذكاء الاصطناعي
  ├── /qdml/create              ← بروتوكول الذكاء الاصطناعي
  ├── /qdml/compile             ← بروتوكول الذكاء الاصطناعي
  ├── /qdml/search              ← بروتوكول الذكاء الاصطناعي
  └── /ws/v3                    ← WebSocket (مزامنة حية)
```

### 4.3 بروتوكول المزامنة (إصلاح MAS Store v3)

يحتوي MAS Store v3 الحالي على فجوتين حرجتين:
1. **عدم نشر الحذف (No delete propagation)**: عندما يتم حذف سجل في الواجهة الخلفية، لا تعلم الواجهة الأمامية بذلك.
2. **عدم وجود سجل تغييرات موثوق**: يتتبع نظام المؤشر (cursor system) الأرقام التسلسلية ولكنه لا يخزن سجلاً دائماً لما تغير.

يطبق نظام AI-First **سجل تغييرات (change-log) كامل**:

```
تعديل في الواجهة الخلفية
  ↓
  ├── كتابة في جدول PostgreSQL
  ├── كتابة في change_log (الإجراء: إدراج/تحديث/حذف)
  ├── إذا كان حذفا: تعيين tombstone=true في change_log
  ├── تعيين cursor_seq (رقم متسلسل)
  └── بث لعملاء WS:
      {
        "type": "server:patch",
        "table": "invoices",
        "action": "delete",       ← جديد: إجراء حذف صريح
        "record": null,
        "recordRef": { "id": "uuid" },
        "cursor": { "sequence": 1542 },
        "tombstone": true          ← جديد: علامة الحذف
      }

إعادة اتصال العميل
  ↓
  ├── إرسال آخر المؤشرات (lastCursors): { "invoices": 1500, "users": 1200 }
  ├── يستعلم الخادم: SELECT * FROM change_log WHERE cursor_seq > $1
  ├── يرسل الخادم حزمة (batch):
      {
        "type": "server:patch.batch",
        "patches": [
          { "table": "invoices", "action": "update", "record": {...} },
          { "table": "invoices", "action": "delete", "tombstone": true, "recordRef": {"id":"..."} }
        ]
      }
  └── يطبق العميل: عمليات الإدراج/التحديث وعمليات الحذف من IndexedDB
```

### 4.4 محرك قواعد الأمان

يتم تعريف الأمان في المخطط، وليس في كود التطبيق:

```json
{
  "access_rules": {
    "read": {
      "scope": "tenant",           
      "field": "tenant_id"          
    },
    "write": {
      "roles": ["admin", "accountant"],
      "own_records": true,          
      "own_field": "created_by"     
    },
    "delete": {
      "roles": ["admin"]
    },
    "secret_fields": ["password_hash", "internal_notes"],
    "locked": false                 
  }
}
```

تفرض بيئة التشغيل هذه القواعد تلقائياً:
- **نطاق القراءة (Read scoping)**: `SELECT * FROM invoices WHERE tenant_id = $user_tenant_id`
- **التحقق من الأدوار (Role checking)**: قبل الكتابة/الحذف، تحقق من مطابقة دور المستخدم
- **تنظيف الحقول (Field sanitization)**: يتم إزالة الحقول السرية من استجابات API
- **قفل الجداول (Table locking)**: ترفض الجداول المقفلة جميع التعديلات

---

## 5. معمارية الواجهة الأمامية (شبيهة بـ Firebase)

### 5.1 مخزن AI-First Store (بديل MAS Store v3)

مخزن الواجهة الأمامية هو طبقة تفاعلية خفيفة فوق IndexedDB، مع مزامنة كاملة:

```javascript
// يكتب الذكاء الاصطناعي هذا في منطق المكون. يتم إنشاء المخزن تلقائياً من المخطط.
const store = AIFirstStore.init({
  schema: projectSchema,  // يتم تحميله تلقائياً من /api/v1/schema
  ws: '/ws/v3',
  auth: { token, userId }
});

// مراقبة مع مزامنة كاملة (الإدراج، التحديث، وأيضاً الحذف)
store.watch('invoices', (rows, meta) => {
  // meta.action: 'snapshot' | 'upsert' | 'delete'
  // إذا كان حذفا: يكون الصف قد أُزيل بالفعل من `rows`
  ctx.setState({ invoices: rows });
}, { filters: { status: 'draft' } });

// CRUD
await store.save('invoices', { ...record });
await store.delete('invoices', recordId);

// تقسيم الصفحات العميقة (بيانات تاريخية، غير حية)
const page = await store.query('invoices', {
  live: false,
  page: 3,
  limit: 50,
  filters: { status: 'posted' },
  before: '2026-01-01'
});
```

### 5.2 IndexedDB المدفوع بالمخطط

يتم إنشاء مخازن IndexedDB تلقائياً من مستند المخطط:

```javascript
// تم إنشاؤه تلقائياً من schema.tables
const dbConfig = {
  name: 'my-erp',
  version: schema.meta.version_int,
  stores: schema.tables.reduce((acc, table) => {
    acc[table.name] = {
      keyPath: 'id',
      indexes: table.fields
        .filter(f => f.references || f.type === 'uuid')
        .map(f => ({ name: f.columnName, keyPath: f.columnName }))
    };
    return acc;
  }, {})
};
```

---

## 6. بروتوكول QDML (المُحسّن)

### 6.1 الكود المصغر مع الوظائف المشتركة والمتغيرات العامة

عندما يطلب الذكاء الاصطناعي `describe` (وصف)، فإنه لا يتلقى شجرة المكونات فحسب، بل يتلقى أيضاً فهرس الوظائف المشتركة والمتغيرات العامة:

```json
{
  "modules": [
    {
      "id": "mod-1", "name": "auth",
      "components": [
        { "id": "cmp-1", "name": "LoginScreen", "kind": "screen",
          "pillars": ["schema","template","logic"],
          "children": [
            { "id": "cmp-2", "name": "AuthInput", "kind": "atom" }
          ]
        }
      ]
    }
  ],
  "shared_functions": [
    { "id": "fn-1", "name": "formatCurrency", "signature": "(amount: number, currency: string) => string", "module": null },
    { "id": "fn-2", "name": "validatePhone", "signature": "(phone: string) => boolean", "module": "auth" }
  ],
  "global_vars": [
    { "name": "API_BASE", "type": "string", "scope": "project" },
    { "name": "SUPPORTED_LANGS", "type": "array", "scope": "project" }
  ],
  "i18n_namespaces": ["auth", "common", "errors"],
  "design_tokens": { "color": 12, "spacing": 8, "radius": 4 },
  "backend_schema_tables": ["users", "invoices", "products"]
}
```

يرى الذكاء الاصطناعي **المعمارية الكاملة** — مكونات الواجهة الأمامية، جداول الواجهة الخلفية، الأدوات المساعدة المشتركة، والتكوين العام — في عرض واحد محجوب التفاصيل (blinded view) قبل الغوص في أي مكون محدد.

### 6.2 الوعي بجداول الواجهة الخلفية

عند تعديل أحد المكونات، يرى الذكاء الاصطناعي أيضاً جداول الواجهة الخلفية المتاحة. يمكّن هذا الذكاء الاصطناعي من ربط استدعاءات API بشكل صحيح:

```json
// تتضمن استجابة الكشف (reveal) سياق الواجهة الخلفية
{
  "component": { "id": "cmp-1", "name": "InvoiceList", ... },
  "pillars": { ... },
  "connected_tables": [
    { "table": "invoices", "access": "read,write", "live": true },
    { "table": "customers", "access": "read", "live": false }
  ]
}
```

---

## 7. عمليات التطوير وبيئة التشغيل (DevOps & Runtime)

### 7.1 التوليد الديناميكي للملفات

يولد النظام جميع ملفات البنية التحتية من قاعدة البيانات:

```
generate(project_id)
  ├── Dockerfile
  ├── docker-compose.yml
  ├── requirements.txt (تبعيات Python)
  ├── package.json (تبعيات Node للواجهة الأمامية)
  ├── tailwind.config.js (من جدول design_token)
  ├── index.css (متغيرات CSS من design_token)
  ├── schema.sql (من مستند المخطط)
  ├── migrations/*.sql (من اختلافات المخطط)
  ├── src/server.py (FastAPI, مولد تلقائياً)
  └── dist/ (الواجهة الأمامية المجمعة)
```

**هذه الملفات عبارة عن مرايا (mirrors).** يتم إعادة إنشائها عند كل أمر `generate`. قاعدة البيانات هي دائماً مصدر الحقيقة.

### 7.2 مرصد التطوير (Dev Observatory)

مستلهماً من منصة Ant-Swarm، يتضمن AI-First مرصد تطوير مدمج:

```
Dev Observatory
  ├── لوحة تحكم حالة المشروع (Project Status Dashboard)
  │   ├── عدد المكونات، عدد الوحدات
  │   ├── عدد جداول المخطط
  │   ├── سجل التعديلات (التغييرات الأخيرة)
  │   └── سجل التغييرات (حالة المزامنة)
  ├── المعاينة الحية (Live Preview)
  │   ├── ترجمة (Compile) وخدمة عند الطلب
  │   ├── إعادة تحميل ساخن (Hot reload) عند تغيير قاعدة البيانات
  │   └── معاينة باستراتيجيات متعددة (ملف واحد، تقسيم وحدات)
  ├── مدقق بناء الجملة (Syntax Checker)
  │   ├── التحقق من جميع أجسام الركائز عند الحفظ
  │   ├── التحقق من مراجع مفاتيح i18n
  │   ├── التحقق من لغة القالب (DSL)
  │   └── الإبلاغ عن الأخطاء للذكاء الاصطناعي
  ├── مشغل الاختبار (Test Runner)
  │   ├── اختبارات متصفح Playwright
  │   ├── اختبارات مسارات واجهة برمجة التطبيقات API
  │   └── اختبارات التحقق من المخطط
  └── واجهة وكيل الذكاء الاصطناعي (AI Agent Interface)
      ├── وحدة تحكم أوامر QDML
      ├── عارض تاريخ التعديلات
      └── ضوابط التراجع (Rollback controls)
```

### 7.3 مسار البناء (Build Pipeline)

```
تغيير في قاعدة البيانات
  → التحقق من بناء الجملة (التحقق من الركائز، i18n، المخطط)
  → الترجمة / Compile (قاعدة البيانات → ملفات عبر الاستراتيجية)
  → البناء / Build (تطهير Tailwind، حزم / bundle)
  → الاختبار (Playwright، اختبارات API)
  → التقرير (الأخطاء → الذكاء الاصطناعي أو الإنسان)
  → النشر / Deploy (بناء Docker ودفعه)
```

### 7.4 توليد Docker

```dockerfile
# تم إنشاؤه تلقائياً من قاعدة البيانات
FROM python:3.12-slim
COPY quantum-core /usr/local/bin/quantum-core
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY generated/ /app/
WORKDIR /app
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 8. معمارية وكيل الذكاء الاصطناعي (AI Agent Architecture)

### 8.1 أدوار الوكيل

| الوكيل (Agent) | المسؤولية | الأدوات |
|-------|---------------|-------|
| **المهندس المعماري (Architect)** | تصميم المخطط، هيكل الوحدات، العلاقات بين الجداول | `qdml/describe`, `qdml/create` |
| **الواجهة الأمامية (Frontend)** | ركائز المكونات (قالب، منطق، نمط) | `qdml/reveal`, `qdml/mutate` |
| **الواجهة الخلفية (Backend)** | جداول المخطط، قواعد الوصول، منطق API | `qdml/schema`, `qdml/mutate` |
| **ضمان الجودة (QA)** | تشغيل الاختبارات، التحقق من بناء الجملة، الإبلاغ عن الأخطاء | `test/run`, `check/syntax` |
| **DevOps** | توليد Docker، النشر، إدارة البيئات | `generate`, `deploy` |

### 8.2 التكامل مع Ant-Swarm

يركب نظام AI-First **كمزود واجهة برمجة تطبيقات نصية** (text API provider) على منصة Ant-Swarm:

```
Ant-Swarm
  ├── مزود الذكاء الاصطناعي (Gemini، Claude، إلخ.)
  │   └── يرسل أوامر QDML عبر واجهة API النصية
  ├── تكامل Playwright
  │   └── يختبر الواجهة الأمامية المجمعة في متصفح حقيقي
  └── خادم AI-First QDML
      └── يتلقى الأوامر، يعدل قاعدة البيانات، ويعيد النتائج
```

توفر واجهة API النصية لـ Ant-Swarm:
1. **توليد النص بالذكاء الاصطناعي**: يرسل الذكاء الاصطناعي لغة طبيعية → يتلقى أوامر QDML
2. **اختبار المتصفح**: يتحقق Playwright من المخرجات المجمعة
3. **حلقة تغذية راجعة للأخطاء**: يتم تغذية أخطاء بناء الجملة وإخفاقات الاختبارات مرة أخرى إلى الذكاء الاصطناعي

---

## 9. اللغات وحزمة التكنولوجيا (Languages & Stack)

| الطبقة (Layer) | التكنولوجيا | السبب |
|-------|-----------|-----|
| **المحرك الأساسي** | C++ (ملف تنفيذي مجمع) | أقصى أداء لـ ORM، بناء الاستعلامات، التحقق من المخطط، عمليات الشجرة |
| **خادم الواجهة الخلفية** | Python (FastAPI) | غلاف رقيق فوق محرك C++ الأساسي. بسيط، غير متزامن، مفهوم جيداً |
| **إطار عمل الواجهة الأمامية** | MAS JS (خاص بنا) | مدفوع بالمخطط، VDOM، الترجمة `t()`، تفويض `gkey` |
| **مخزن الواجهة الأمامية** | AI-First Store (JS) | واجهة برمجة تطبيقات شبيهة بـ Firebase، IndexedDB، مزامنة WS مع سجل تغييرات |
| **قاعدة البيانات** | PostgreSQL 16+ | JSONB، FTS، التقسيم (partitioning)، الوصول المتزامن |
| **الأنماط والتنسيق** | Tailwind CSS + متغيرات CSS | فئات أدوات مساعدة أصلية للذكاء الاصطناعي، تخصيص מظهر مدفوع بقاعدة البيانات |
| **الاختبار** | Playwright | اختبار متصفح حقيقي، متكامل مع Ant-Swarm |
| **النشر** | Docker + Linux | ملفات Docker مولدة تلقائياً، هدف Linux |

---

## 10. خطة التنفيذ

### المرحلة 1: النواة (الأسبوع 1-2)
| الخطوة | المهمة | المخرجات |
|------|------|--------|
| 1 | تصميم تنسيق مستند المخطط الرئيسي (توسيع عقد Quantum) | `schema-contract.json` |
| 2 | بناء محرك C++ الأساسي: مولد DDL + منشئ الاستعلامات + مدقق المخطط | ملف تنفيذي `quantum-core` |
| 3 | إنشاء مخطط PostgreSQL لنموذج المكونات (الوحدة، المكون، الركيزة، إلخ) | `schema.sql` |
| 4 | بناء خادم Python FastAPI QDML | `server.py` |
| 5 | تنفيذ جدول change_log + بروتوكول المزامنة | سجل تغييرات مع علامات الحذف (tombstones) |

### المرحلة 2: مخزن الواجهة الأمامية (الأسبوع 2-3)
| الخطوة | المهمة | المخرجات |
|------|------|--------|
| 6 | بناء AI-First Store (يحل محل MAS Store v3) | `ai-first-store.js` |
| 7 | تنفيذ مزامنة الاختلافات الكاملة مع نشر عمليات الحذف | متوافق مع WS v3 |
| 8 | بناء مترجم (compiler) بسيط (استراتيجية الملف الواحد) | `compiler.py` |
| 9 | زرع (Seed) مشروع اختباري (وحدتين، 5 مكونات) | عرض توضيحي (demo) يعمل من البداية للنهاية |

### المرحلة 3: تكامل الذكاء الاصطناعي (الأسبوع 3-4)
| الخطوة | المهمة | المخرجات |
|------|------|--------|
| 10 | تركيب QDML كمزود واجهة برمجة تطبيقات نصية لـ Ant-Swarm | تكامل API |
| 11 | بناء مدقق بناء الجملة (التحقق من الركائز، فحص i18n) | `checker.py` |
| 12 | دمج مشغل اختبار Playwright | مسار اختبار المتصفح |
| 13 | بناء مرصد التطوير (لوحة تحكم الحالة، معاينة حية) | واجهة مستخدم ويب (Web UI) |

### المرحلة 4: أول مشروع حقيقي (الأسبوع 4+)
| الخطوة | المهمة | المخرجات |
|------|------|--------|
| 14 | يبني الذكاء الاصطناعي وحدة ERP كاملة من الصفر باستخدام AI-First | إثبات المفهوم (Proof of concept) |
| 15 | اختبار الدورة الكاملة: المخطط → قاعدة البيانات → المكونات → الترجمة → الاختبار → النشر | تحقق من البداية للنهاية |
| 16 | بناء توليد Docker من قاعدة البيانات | نشر تلقائي (Auto-deployment) |

---

## 11. سجل الاتفاقيات والقرارات

| # | القرار | الحالة |
|---|----------|--------|
| 1 | المخطط أولاً: مستند JSON واحد يدفع كل شيء (قاعدة البيانات، API، الواجهة الأمامية، الأمان) | ✅ نهائي |
| 2 | PostgreSQL فقط. قاعدة بيانات واحدة لكل مشروع. | ✅ نهائي |
| 3 | محرك أساسي C++ لـ ORM، بناء الاستعلامات، DDL، عمليات الشجرة | ✅ نهائي |
| 4 | Python (FastAPI) كغلاف للخادم | ✅ نهائي |
| 5 | سجل تغييرات كامل مع علامات حذف (tombstones) لنشر عمليات الحذف | ✅ نهائي |
| 6 | قواعد الأمان المحددة في المخطط، والمفروضة بواسطة بيئة التشغيل | ✅ نهائي |
| 7 | الوظائف المشتركة والمتغيرات العامة مفهرسة في الكود المصغر (Mini Code) | ✅ نهائي |
| 8 | وحدة الواجهة الأمامية = وحدة الواجهة الخلفية. نفس المعرف (ID)، نفس مصدر الحقيقة | ✅ نهائي |
| 9 | لا توجد ملفات ثابتة. يتم توليد كل شيء من قاعدة البيانات | ✅ نهائي |
| 10 | تكامل Ant-Swarm لواجهة برمجة التطبيقات النصية للذكاء الاصطناعي + اختبار Playwright | ✅ نهائي |
| 11 | نشر Docker + Linux. ملفات Docker مولدة تلقائياً | ✅ نهائي |
| 12 | مرصد التطوير: لوحة تحكم مدمجة، معاينة حية، الإبلاغ عن الأخطاء | ✅ نهائي |
| 13 | Tailwind CSS + متغيرات CSS لتخصيص المظهر | ✅ نهائي |
| 14 | مفتاح i18n أولاً مع `t()`. يتحقق المترجم من جميع مراجع المفاتيح | ✅ نهائي |
| 15 | سجل التعديلات + سجل التغييرات: كل تغيير يتم تتبعه ويمكن التراجع عنه | ✅ نهائي |
