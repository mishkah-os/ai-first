# MAS Schema-Driven Architecture (`mas-schema.js`)

> **Standard**: Enhanced JSON Schema / Database Definition
> **Role**: Runtime Validation, Introspection, Auto-generation (Backend/Frontend), and ERD
> **Namespace**: `MAS.Schema`

## 1. Overview & Core Concept

في نظام MAS (MAS)، الهيكل `Schema` ليس مجرد ملف للتوثيق؛ بل هو **القلب النابض والمحرك الأساسي** (Executable Code) للتطبيق بالكامل. تم تصميم النظام ليعمل بمبدأ **"القيادة بالهيكل" (Schema-Driven)**.

### لماذا نبدأ دائماً بملف الـ Schema والـ Seeds؟

سواء كنت تعمل كمطور واجهات (Frontend) أو مطور نظام خلفي (Backend)، **الخطوة رقم 1 في أي مشروع هي كتابة ملف الـ Schema (هيكل الجداول) وملف الـ Seeds (البيانات الأولية)**.

- **بالنسبة لمطور الواجهات (Frontend Only):**
  إنشاء ملف `schema.js` (أو `schema.json`) و `seeds.json` يجبرك على التفكير في شكل البيانات (Data Models/State) قبل بدء التصميم. سيستخدم النظام هذا الهيكل لعمل Validation، تلميحات للـ UI، وبناء جداول محلية وهمية (Mocked DB).
- **التمهيد للنظام الخلفي (Backend Transition):**
  بمجرد كتابتك لملف الهيكل في الواجهة الأمامية، فإنك فعلياً كتبت الكود الخاص بقاعدة البيانات! سيقوم محرك الباك إند لاحقاً (مثل الـ C++ Hybrid Engine أو الـ ORM الموجود في `src/orm`) بقراءة نفس الملف **لإنشاء جداول SQL تلقائياً**، بناء الـ ORM Models، وإنشاء الـ REST APIs (مثل عمليات الحفظ، التعديل الحذف) بدون كتابة سطر كود إضافي في الباك إند.

---

## 2. الهيكل التشريحي لـ Schema (How it works)

ملف الـ Schema (مثل `clinic_schema.json` أو ملف الـ schema الخاص بمشروعك) يتكون من الأقسام المترابطة التالية:

### أ) البيانات المرجعية (Modules & Table Types)

تعريف الوحدات الأساسية للمشروع (مثل `Core`, `Healthcare`, `Financial`) وتصنيفات الجداول لتسهيل العرض والتنظيم.

### ب) تعريف الجداول (Tables)

كل جدول يحتوي على:

- `name` / `sqlName`: اسم الجدول الدقيق الذي سيتم إنشاؤه في قاعدة البيانات.
- `fields`: أعمدة الجدول، وهي الأكثر أهمية. أنواعها معرّفة مسبقاً في `mas-schema.js` وتغطّي كل أنواع SQL (مثل `uuid`, `nvarchar`, `integer`, `boolean`, `datetime`, `json`).
- `smart_features`: ميزات إضافية ذكية للواجهة (UI) تحدد كيف يتم عرض هذا الجدول (أيقونات، ألوان، قواعد العرض `display_rule`، وحقول العرض في الجداول).
- `cache_policy`: سياسات التخزين المؤقت (مثلاً `offline-first` مع `sync: realtime`)، وهذا مهم جداً للتطبيقات التي تعمل بدون إنترنت (PWA).

**مثال مصغر لجدول:**

```json
{
  "name": "clinic_patients",
  "sqlName": "clinic_patients",
  "fields": [
    { "name": "id", "type": "uuid", "primaryKey": true, "nullable": false },
    { "name": "first_name", "type": "nvarchar", "maxLength": 100, "nullable": false },
    { "name": "dob", "type": "date", "nullable": true }
  ],
  "smart_features": {
    "module_id": "operations_patients",
    "settings": { "icon": "🧍" }
  }
}
```

---

## 3. البيانات الأساسية - ملف الـ Seeds (`initial.json`)

ملامح الـ Schema-driven لا تكتمل بدون بيانات البذور (Seeds).
في بداية المشروع، نقوم بإنشاء ملف (مثل `seeds/initial.json`) يحتوي على البيانات الافتراضية للجداول (مثلاً: اللغات `languages`، الإعدادات الأساسية، الكيانات المبدئية مثل أنواع العيادات).

**أهمية الـ Seeds:**

- يفيد مطور الـ Frontend كبيانات حقيقية للعرض بدلاً من بيانات وهمية عشوائية.
- يستخدمه محرك الـ Backend لاحقاً لعمل `INSERT` لهذه البيانات الافتراضية عند تجهيز بيئة الإنتاج (Production).

---

## 4. نظام الـ ERD (توليد المخططات التلقائي)

النظام مزود بمتصفح ذكي للمخططات `erd.html` (يعتمد على مكتبة AntV X6).
عند كتابة ملف الـ Schema (بما في ذلك العلاقات `references`)، يقوم نظام الـ ERD بقراءته وعرضه بشكل مرئي متكامل!
هذا يزيل الحاجة لاستخدام أدوات خارجية لتصميم قواعد البيانات (Database Design). الـ Schema الخاصة بك توثّق نفسها مرئياً.

---

## 5. محرك Validation & Introspection (الـ Schema Engine)

محرك الـ Schema الموجود في `mas-schema.js` يقدم فئات (Classes) قوية جدأً لقراءة وتنفيذ المهام بناءً على الهيكل الـ JSON:

### `Schema.Table` & `Schema.Field`

يحلل الحقول ويطبّق قواعد صارمة:

- تحويل البيانات للنمط الصحيح (Normalization) (مثلاً التأكد من أنّ الـ `boolean` فعلاً `true/false` أو `1/0`).
- تطبيق القيم الافتراضية `applyDefault`.
- توليد أوامر SQL لإنشاء الجدول (`columnSQL` و `toSQL`): كل حقل لديه دالة لتوليد كود الـ SQL الخاص به!

### `Schema.Registry`

مدير الهيكل بالكامل:

- `register(table)`: تسجيل الجداول.
- `createRecord(tableName, data)` / `updateRecord`: عمليات معالجة للبيانات قبل حفظها (تفيد جداً في الواجهة للتأكد من صحة الدخل قبل حتى إرساله للـ Backend).
- `generateSQL()`: يقوم بترتيب الجداول طبولوجياً (`topologicallySorted`) بناءً على العلاقات الدورية (Foreign Keys) ويقوم بطباعة كود الـ SQL لإنشاء قاعدة البيانات بالكامل.

---

## 6. سير العمل المقترح (Workflow Example)

لتوضيح كيف يجب أن يبدأ المشروع (مثل `dashboard/legendary` المذكور كمثال):

1. **تقسيم المشروع المنطقي:** يجب أن يحتوي مجلد المشروع على ملفات واضحة، أولها الهيكل.
   - `schema.json` -> تعريف هيكل البيانات.
   - `seeds.json` -> البيانات الافتراضية.
   - `data.js` -> يقرأ من الـ Schema أو يستقبل المزامنة.
   - `functions.js` -> الوظائف المنطقية.
   - `orders.js` -> أوامر التفاعل (Events).
   - `ui.js` -> مكونات العرض (DSL).
   - `app.js` -> دمج الجميع.

2. **كتابة الهيكل:** يبدأ المبرمج بكتابة الـ `schema.json` ويحدد الجداول التي يحتاجها (مثلاً: `orders`, `users`)، ويحدد الـ `seeds.json`.
3. **تصميم الواجهة:** يستخدم المبرمج ملف `erd.html` ليرى المخطط الخاص به. يبدأ ببناء شاشات الـ UI التي تقرأ البيانات من هذا الهيكل وتتعامل مع الـ Validation الخاص به `MAS.schema.Registry`.
4. **الانتقال للـ Backend (تلقائياً تقريباً):** تُأخذ ملفات `schema.json` و `seeds.json` وتوضع في مسارات خاصة في نظام الباك إند `os/src/orm` وتقوم الواجهات البرمجية (APIs) والـ ORM بالتولّد أوتوماتيكياً!

> **الخلاصة:**
> "اكتب الهيكل مرة واحدة، دعه يولد واجهات العرض (UI Hints)، ويدير التحقق (Validation)، ويرسم مخططاتك (ERD)، ويبني خوادمك (Backend & Database)."
