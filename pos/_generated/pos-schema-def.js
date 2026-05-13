// POS Schema: mishkah_pos v1
// 57 tables, 564 fields
// Auto-generates PostgreSQL DDL via Quantum Core

const POS_SCHEMA = {
  "name": "mishkah_pos",
  "version": 1,
  "table_count": 57,
  "tables": [
    {
      "name": "pos_database",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "branchId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "payload",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "createdAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "updatedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "pos_terminal",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "code",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "label",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "number",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "locationId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "zone",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "type",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "status",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "timezone",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "lastOnlineAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "createdAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "updatedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "audit_events",
      "fields": [
        {
          "name": "action",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "meta",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "occurredAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "refId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "refType",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "userId",
          "type": "string",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "category_sections",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "categoryId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "sectionId",
          "type": "string",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "customer_addresses",
      "fields": [
        {
          "name": "apartment",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "areaId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "building",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "customerId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "floor",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "isPrimary",
          "type": "boolean",
          "required": false,
          "primary": false
        },
        {
          "name": "label",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "notes",
          "type": "text",
          "required": false,
          "primary": false
        },
        {
          "name": "street",
          "type": "string",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "delivery_zones",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "name",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "deliveryFee",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "isActive",
          "type": "boolean",
          "required": false,
          "primary": false
        },
        {
          "name": "governorate",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "city",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "area",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "currency",
          "type": "string",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "customer_profiles",
      "fields": [
        {
          "name": "createdAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "email",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "discountPercent",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "name",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "notes",
          "type": "text",
          "required": false,
          "primary": false
        },
        {
          "name": "phone",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "customerType",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "phones",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "preferredLanguage",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "updatedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "delivery_drivers",
      "fields": [
        {
          "name": "id",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "isActive",
          "type": "boolean",
          "required": false,
          "primary": false
        },
        {
          "name": "name",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "phone",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "vehicleId",
          "type": "string",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "dining_tables",
      "fields": [
        {
          "name": "displayOrder",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "name",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "note",
          "type": "text",
          "required": false,
          "primary": false
        },
        {
          "name": "seats",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "state",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "zone",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "version",
          "type": "integer",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "employees",
      "fields": [
        {
          "name": "allowedDiscountRate",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "createdAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "email",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "fullName",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "hiredAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "phone",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "pinCode",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "role",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "status",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "updatedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "expo_pass_ticket",
      "fields": [
        {
          "name": "callAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "createdAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "deliveredAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "holdReason",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "jobOrderIds",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "meta",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "orderId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "batchId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "orderNumber",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "readyItems",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "runnerId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "runnerName",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "status",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "totalItems",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "updatedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "job_order_detail",
      "fields": [
        {
          "name": "allergens",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "categoryId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "createdAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "finishAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "itemId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "itemNameAr",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "itemNameEn",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "itemSku",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "jobOrderId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "lastActionBy",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "meta",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "orderLineId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "posLineRevision",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "prepNotes",
          "type": "text",
          "required": false,
          "primary": false
        },
        {
          "name": "uniqueId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "priority",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "quantity",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "startAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "status",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "unit",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "updatedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "job_order_detail_modifier",
      "fields": [
        {
          "name": "createdAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "detailId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "isRequired",
          "type": "boolean",
          "required": false,
          "primary": false
        },
        {
          "name": "meta",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "modifierType",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "nameAr",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "nameEn",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "notes",
          "type": "text",
          "required": false,
          "primary": false
        },
        {
          "name": "quantity",
          "type": "decimal",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "job_order_header",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "orderId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "orderNumber",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "posRevision",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "orderTypeId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "serviceMode",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "stationId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "stationCode",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "status",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "progressState",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "totalItems",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "completedItems",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "remainingItems",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "hasAlerts",
          "type": "boolean",
          "required": false,
          "primary": false
        },
        {
          "name": "isExpedite",
          "type": "boolean",
          "required": false,
          "primary": false
        },
        {
          "name": "tableLabel",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "customerName",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "dueAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "acceptedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "startedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "readyAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "completedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "expoAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "syncChecksum",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "notes",
          "type": "text",
          "required": false,
          "primary": false
        },
        {
          "name": "batchId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "meta",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "createdAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "updatedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "job_order_status_history",
      "fields": [
        {
          "name": "actorId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "actorName",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "actorRole",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "changedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "jobOrderId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "meta",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "reason",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "status",
          "type": "string",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "job_order_batch",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "orderId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "orderNumber",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "status",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "totalJobs",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "readyJobs",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "batchType",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "assembledAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "servedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "notes",
          "type": "text",
          "required": false,
          "primary": false
        },
        {
          "name": "meta",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "createdAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "updatedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "batch_create_log",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "batchId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "orderId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "branchId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "moduleId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "batchSequence",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "batchType",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "totalJobs",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "lineCount",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "itemQty",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "source",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "status",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "meta",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "createdAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "updatedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "kitchen_sections",
      "fields": [
        {
          "name": "descriptionAr",
          "type": "text",
          "required": false,
          "primary": false
        },
        {
          "name": "descriptionEn",
          "type": "text",
          "required": false,
          "primary": false
        },
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "nameAr",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "nameEn",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "sortOrder",
          "type": "integer",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "menu_categories",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "nameAr",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "nameEn",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "sectionId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "sortOrder",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "isActive",
          "type": "boolean",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "menu_items",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "sku",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "categoryId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "kitchenSectionId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "nameAr",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "nameEn",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "descriptionAr",
          "type": "text",
          "required": false,
          "primary": false
        },
        {
          "name": "descriptionEn",
          "type": "text",
          "required": false,
          "primary": false
        },
        {
          "name": "basePrice",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "taxGroupId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "isCombo",
          "type": "boolean",
          "required": false,
          "primary": false
        },
        {
          "name": "isActive",
          "type": "boolean",
          "required": false,
          "primary": false
        },
        {
          "name": "favoriteRank",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "sort",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "image",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "media",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "createdAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "updatedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "menu_item_media",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "itemId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "type",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "url",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "isPrimary",
          "type": "boolean",
          "required": false,
          "primary": false
        },
        {
          "name": "createdAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "menu_item_modifier",
      "fields": [
        {
          "name": "itemId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "modifierId",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "isDefault",
          "type": "boolean",
          "required": false,
          "primary": false
        },
        {
          "name": "maxQuantity",
          "type": "integer",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "menu_item_price",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "itemId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "priceType",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "label",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "amount",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "currency",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "isDefault",
          "type": "boolean",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "menu_modifiers",
      "fields": [
        {
          "name": "id",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "isActive",
          "type": "boolean",
          "required": false,
          "primary": false
        },
        {
          "name": "modifierType",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "nameAr",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "nameEn",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "priceChange",
          "type": "decimal",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "order_delivery",
      "fields": [
        {
          "name": "deliveredAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "dispatchedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "driverId",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "notes",
          "type": "text",
          "required": false,
          "primary": false
        },
        {
          "name": "orderId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "status",
          "type": "string",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "order_header",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "fullId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "shiftId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "posId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "posNumber",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "orderTypeId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "statusId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "stageId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "paymentStateId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "cashierFinalization",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "cashierFinalized",
          "type": "boolean",
          "required": false,
          "primary": false
        },
        {
          "name": "cashierFinalizedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "cashierFinalizedBy",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "tableId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "customerId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "customerAddressId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "driverId",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "openedBy",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "closedBy",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "openedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "closedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "guests",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "notes",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "subtotal",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "discount",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "service",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "tax",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "deliveryFee",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "totalDue",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "totalPaid",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "metadata",
          "type": "json",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "order_line",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "itemId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "kitchenSectionId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "metadata",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "notes",
          "type": "text",
          "required": false,
          "primary": false
        },
        {
          "name": "orderId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "batchId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "batchSequence",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "kdsPublishState",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "kdsSaveToken",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "parentLineId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "quantity",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "statusId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "total",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "unitPrice",
          "type": "decimal",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "order_line_modifier",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "lineId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "modifierId",
          "type": "integer",
          "required": false,
          "primary": false
        },
        {
          "name": "modifierType",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "priceChange",
          "type": "decimal",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "order_line_statuses",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "nameAr",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "nameEn",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "sequence",
          "type": "integer",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "order_line_status_log",
      "fields": [
        {
          "name": "actorId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "changedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "metadata",
          "type": "json",
          "required": false,
          "primary": false
        },
        {
          "name": "orderId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "orderLineId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "source",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "stationId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "statusId",
          "type": "string",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "order_payment",
      "fields": [
        {
          "name": "amount",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "capturedAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "orderId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "paymentMethodId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "reference",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "shiftId",
          "type": "string",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "shift_payment_ledger",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "branchId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "moduleId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "orderId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "orderType",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "paymentId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "shiftId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "erpUserId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "direction",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "entryKind",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "amount",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "method",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "referenceType",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "referenceId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "reversalOfEntryId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "createdAt",
          "type": "timestamp",
          "required": false,
          "primary": false
        },
        {
          "name": "actorId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "actorName",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "payload",
          "type": "json",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "order_payment_state",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "nameAr",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "nameEn",
          "type": "string",
          "required": false,
          "primary": false
        }
      ]
    },
    {
      "name": "order_refund",
      "fields": [
        {
          "name": "amount",
          "type": "decimal",
          "required": false,
          "primary": false
        },
        {
          "name": "id",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "paymentId",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "reason",
          "type": "string",
          "required": false,
          "primary": false
        },
        {
          "name": "refundedAt",
          "type": "timestamp",
       