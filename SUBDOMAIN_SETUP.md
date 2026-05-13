# إعداد Subdomain لمشروع AI-First

## ملخص الإعداد

تم إعداد subdomain **first.ai-auto.cloud** لمشروع **ai-first** بنجاح.

## التفاصيل

### 1. المشروع
- **المسار**: `/srv/apps/ai-first`
- **النوع**: QDML Platform - FastAPI Application
- **البورت**: `8001`
- **قاعدة البيانات**: PostgreSQL (مشتركة على البورت 5432)

### 2. Nginx Configuration
- **الملف**: `/etc/nginx/sites-available/first.ai-auto.cloud`
- **الحالة**: مفعّل ويعمل
- **البروتوكول**: HTTP (SSL غير متاح حالياً بسبب عدم وجود DNS record)

### 3. الخدمة
الخدمة تعمل بالفعل على البورت 8001 (خدمة Python موجودة مسبقاً)
- لا حاجة لخدمة systemd إضافية
- الخدمة تعمل بشكل مستقر

### 4. الوصول
- **HTTP**: http://first.ai-auto.cloud/
- **Local**: http://127.0.0.1:8001/

## API Endpoints

```json
{
    "service": "QDML Platform",
    "version": "3.0.0",
    "endpoints": {
        "auth": "/api/auth/login",
        "qdml": "/api/qdml",
        "compile": "/api/compile/{component}",
        "ai": "/api/ai",
        "kits": "/api/kits",
        "pipelines": "/api/kits/pipelines",
        "stats": "/api/qdml/stats",
        "mini": "/api/qdml/mini/{project}",
        "health": "/health",
        "admin": "/admin"
    }
}
```

## اختبار الخدمة

```bash
# اختبار محلي
curl http://127.0.0.1:8001/

# اختبار health endpoint
curl http://127.0.0.1:8001/health

# اختبار stats
curl http://127.0.0.1:8001/api/qdml/stats
```

## الحصول على SSL Certificate

عندما يكون DNS record جاهز:

```bash
# 1. تأكد من DNS
dig +short first.ai-auto.cloud

# 2. احصل على الشهادة
certbot certonly --webroot -w /var/www/html -d first.ai-auto.cloud

# 3. حدّث nginx config
# استخدم الملف في /etc/nginx/sites-available/first.ai-auto.cloud
# أضف SSL configuration

# 4. أعد تحميل nginx
nginx -t && systemctl reload nginx
```

## Pipeline Script

تم إنشاء سكريبت pipeline جاهز لإضافة subdomains جديدة:

**الموقع**: `/srv/apps/scripts/add-subdomain.sh`

**الاستخدام**:
```bash
/srv/apps/scripts/add-subdomain.sh <subdomain> <port> <app_path> [service_type]
```

**مثال**:
```bash
/srv/apps/scripts/add-subdomain.sh test.ai-auto.cloud 8002 /srv/apps/test-app docker
```

**التوثيق الكامل**: `/srv/apps/scripts/SUBDOMAIN_PIPELINE_README.md`

## الملفات المنشأة

1. `/etc/nginx/sites-available/first.ai-auto.cloud` - nginx config
2. `/etc/nginx/sites-enabled/first.ai-auto.cloud` - symbolic link
3. `/srv/apps/ai-first/core/Dockerfile` - Docker image للمشروع
4. `/srv/apps/ai-first/core/requirements.txt` - Python dependencies
5. `/srv/apps/scripts/add-subdomain.sh` - Pipeline script
6. `/srv/apps/scripts/SUBDOMAIN_PIPELINE_README.md` - توثيق Pipeline

## ملاحظات مهمة

### DNS Configuration
لتفعيل الـ subdomain بشكل كامل، يجب إضافة DNS record:

```
Type: A
Name: first
Value: [IP Address of Server]
TTL: 300
```

### SSL Certificate
بعد إعداد DNS، يمكن الحصول على شهادة SSL مجانية من Let's Encrypt.

### البورت 8001
البورت 8001 مستخدم بالفعل من قبل خدمة Python تعمل على المشروع.
لا حاجة لإنشاء خدمة systemd جديدة.

## الخطوات التالية

1. ✅ إعداد nginx config
2. ✅ تفعيل nginx
3. ✅ التحقق من الخدمة على البورت 8001
4. ⏳ إعداد DNS record (يحتاج تدخل يدوي)
5. ⏳ الحصول على SSL certificate (بعد DNS)

## الدعم

للمزيد من المعلومات:
- راجع `/srv/apps/scripts/SUBDOMAIN_PIPELINE_README.md`
- راجع `/srv/apps/ai-first/README.md`
- راجع `/srv/apps/ai-first/DOCUMENTATION.md`

## أوامر مفيدة

```bash
# فحص nginx
nginx -t
systemctl status nginx
tail -f /var/log/nginx/access.log

# فحص الخدمة
ss -tlnp | grep 8001
curl http://127.0.0.1:8001/health

# إدارة nginx
systemctl reload nginx
systemctl restart nginx
```

---

**تاريخ الإنشاء**: 2026-05-12  
**الحالة**: ✅ جاهز للاستخدام (HTTP فقط - بانتظار DNS لـ SSL)
