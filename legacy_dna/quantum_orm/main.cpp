#include <arpa/inet.h>
#include <cerrno>
#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <fstream>
#include <iostream>
#include <map>
#include <netinet/in.h>
#include <nlohmann/json.hpp>
#include <optional>
#include <postgresql/libpq-fe.h>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <sys/socket.h>
#include <sys/types.h>
#include <thread>
#include <unistd.h>
#include <vector>

using json = nlohmann::json;

namespace {

std::string trim(const std::string &value) {
  std::size_t start = value.find_first_not_of(" \t\r\n");
  if (start == std::string::npos) {
    return "";
  }

  std::size_t end = value.find_last_not_of(" \t\r\n");
  return value.substr(start, end - start + 1);
}

std::string toLower(std::string value) {
  for (char &ch : value) {
    ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
  }
  return value;
}

std::string quoteIdent(const std::string &name) {
  std::string value = trim(name);
  if (value.empty()) {
    throw std::runtime_error("Identifier is required");
  }

  std::string out = "\"";
  for (char ch : value) {
    if (ch == '"') {
      out += "\"\"";
    } else {
      out += ch;
    }
  }
  out += "\"";
  return out;
}

std::optional<long long> parseIntegerLike(const json &value) {
  if (value.is_null()) {
    return std::nullopt;
  }

  try {
    if (value.is_number_integer()) {
      return value.get<long long>();
    }
    if (value.is_number()) {
      return static_cast<long long>(value.get<double>());
    }
    std::string text = trim(value.is_string() ? value.get<std::string>() : value.dump());
    if (text.empty()) {
      return std::nullopt;
    }
    return std::stoll(text);
  } catch (...) {
    return std::nullopt;
  }
}

std::optional<bool> parseBooleanLike(const json &value) {
  if (value.is_null()) {
    return std::nullopt;
  }

  if (value.is_boolean()) {
    return value.get<bool>();
  }

  std::string text = toLower(trim(value.is_string() ? value.get<std::string>() : value.dump()));
  if (text == "1" || text == "true" || text == "yes" || text == "on") {
    return true;
  }
  if (text == "0" || text == "false" || text == "no" || text == "off") {
    return false;
  }
  return std::nullopt;
}

std::string escapeLike(const std::string &value) {
  std::string out;
  out.reserve(value.size());
  for (char ch : value) {
    if (ch == '\\' || ch == '%' || ch == '_') {
      out += '\\';
    }
    out += ch;
  }
  return out;
}

std::string jsonToPgArray(const std::vector<std::string> &items) {
  std::string out = "{";
  for (std::size_t index = 0; index < items.size(); ++index) {
    if (index) {
      out += ",";
    }
    out += "\"";
    for (char ch : items[index]) {
      if (ch == '"' || ch == '\\') {
        out += '\\';
      }
      out += ch;
    }
    out += "\"";
  }
  out += "}";
  return out;
}

std::string stringifyValue(const json &value) {
  if (value.is_null()) {
    return "";
  }
  if (value.is_string()) {
    return value.get<std::string>();
  }
  if (value.is_boolean()) {
    return value.get<bool>() ? "true" : "false";
  }
  if (value.is_number()) {
    return value.dump();
  }
  return value.dump();
}

std::string jsonString(const json &value, const char *key, const std::string &fallback = "") {
  if (!value.is_object() || !value.contains(key) || value[key].is_null()) {
    return fallback;
  }
  if (value[key].is_string()) {
    return value[key].get<std::string>();
  }
  return value[key].dump();
}

int jsonInt(const json &value, const char *key, int fallback = 0) {
  if (!value.is_object() || !value.contains(key) || value[key].is_null()) {
    return fallback;
  }
  if (value[key].is_number_integer()) {
    return value[key].get<int>();
  }
  try {
    return std::stoi(stringifyValue(value[key]));
  } catch (...) {
    return fallback;
  }
}

bool jsonBool(const json &value, const char *key, bool fallback = false) {
  if (!value.is_object() || !value.contains(key) || value[key].is_null()) {
    return fallback;
  }
  if (value[key].is_boolean()) {
    return value[key].get<bool>();
  }
  std::optional<bool> parsed = parseBooleanLike(value[key]);
  return parsed.has_value() ? *parsed : fallback;
}

int jsonIntOrString(const json &value, const char *key, int fallback = 0) {
  return jsonInt(value, key, fallback);
}

json unwrapInputValue(const json &value) {
  if (value.is_object() && value.contains("id")) {
    return value["id"];
  }
  return value;
}

const char *envOrDefault(const char *name, const char *fallback) {
  const char *value = std::getenv(name);
  return value && *value ? value : fallback;
}

std::string join(const std::vector<std::string> &parts, const std::string &delimiter) {
  std::string out;
  for (std::size_t index = 0; index < parts.size(); ++index) {
    if (index) {
      out += delimiter;
    }
    out += parts[index];
  }
  return out;
}

struct ColumnMeta {
  std::string name;
  std::string trans_name;
  std::string data_type;
  std::string type;
  int max_length = 0;
  bool is_nullable = true;
  bool is_identity = false;
  bool is_primary_key = false;
  bool isreferences = false;
  std::string referenced_table;
  std::string referenced_column_name = "id";
  std::string search_columns;
  std::string all_columns;
  std::string component;
  json default_value = nullptr;
  bool is_table_show = true;
  bool is_edit_show = true;
  bool is_searchable = false;
};

struct ObjectMeta {
  std::string name;
  std::vector<ColumnMeta> columns;
};

ColumnMeta parseColumn(const json &value) {
  ColumnMeta column;
  column.name = jsonString(value, "name");
  column.trans_name = jsonString(value, "trans_name");
  column.data_type = toLower(jsonString(value, "data_type"));
  column.type = jsonString(value, "type");
  column.max_length = jsonInt(value, "max_length", 0);
  column.is_nullable = jsonBool(value, "is_nullable", true);
  column.is_identity = jsonBool(value, "is_identity", false);
  column.is_primary_key = jsonBool(value, "is_primary_key", false);
  column.isreferences = jsonBool(value, "isreferences", false);
  column.referenced_table = jsonString(value, "ReferencedTable");
  column.referenced_column_name = jsonString(value, "ReferencedColumnName", "id");
  column.search_columns = jsonString(value, "search_columns");
  column.all_columns = jsonString(value, "all_columns");
  column.component = jsonString(value, "component");
  column.default_value = value.contains("default_value") ? value["default_value"] : json(nullptr);
  column.is_table_show = jsonBool(value, "is_table_show", true);
  column.is_edit_show = jsonBool(value, "is_edit_show", true);
  column.is_searchable = jsonBool(value, "is_searchable", false);
  return column;
}

ObjectMeta parseObjectMeta(const json &value) {
  if (!value.is_object()) {
    throw std::runtime_error("Object metadata is missing");
  }

  ObjectMeta object;
  object.name = value.value("name", "");
  if (object.name.empty()) {
    throw std::runtime_error("Object name is required");
  }

  if (!value.contains("columns") || !value["columns"].is_array()) {
    throw std::runtime_error("Object columns are required");
  }

  for (const json &columnValue : value["columns"]) {
    object.columns.push_back(parseColumn(columnValue));
  }

  return object;
}

const ColumnMeta *findColumn(const ObjectMeta &object, const std::string &name) {
  std::string target = toLower(trim(name));
  if (target.empty()) {
    return nullptr;
  }

  for (const ColumnMeta &column : object.columns) {
    if (toLower(column.name) == target || (!column.trans_name.empty() && toLower(column.trans_name) == target)) {
      return &column;
    }
  }
  return nullptr;
}

std::map<std::string, std::string> buildAliasMap(const ObjectMeta &object) {
  std::map<std::string, std::string> aliases;
  for (const ColumnMeta &column : object.columns) {
    std::string canonical = trim(column.name);
    if (canonical.empty()) {
      continue;
    }
    aliases[toLower(canonical)] = canonical;
    if (!column.trans_name.empty()) {
      aliases[toLower(column.trans_name)] = canonical;
    }
    if (canonical == "tenant_id") {
      aliases["company_id"] = canonical;
      aliases["compid"] = canonical;
    }
    if (canonical == "created_at") {
      aliases["begin_date"] = canonical;
    }
    if (canonical == "updated_at") {
      aliases["last_update"] = canonical;
    }
    if (canonical == "created_by") {
      aliases["user_insert"] = canonical;
    }
  }
  return aliases;
}

std::optional<std::string> resolveColumnName(const ObjectMeta &object, const std::string &inputName) {
  std::map<std::string, std::string> aliases = buildAliasMap(object);
  auto found = aliases.find(toLower(trim(inputName)));
  if (found == aliases.end()) {
    return std::nullopt;
  }
  return found->second;
}

const ColumnMeta *getPrimaryKey(const ObjectMeta &object) {
  for (const ColumnMeta &column : object.columns) {
    if (column.is_primary_key) {
      return &column;
    }
  }
  return nullptr;
}

std::string getRecordsetType(const ColumnMeta &column) {
  std::string type = toLower(column.data_type);
  if (type == "bit") return "boolean";
  if (type == "date") return "date";
  if (type == "datetime" || type == "datetime2") return "timestamptz";
  if (type == "decimal" || type == "numeric") return "numeric";
  if (type == "bigint") return "bigint";
  if (type == "int" || type == "integer") return "integer";
  if (type == "smallint") return "smallint";
  if (type == "json" || type == "jsonb") return "jsonb";
  return "text";
}

json formatCellForOutput(const ColumnMeta &column, const std::string &value) {
  if (column.data_type == "bit") {
    return value == "t" || value == "true" || value == "1" ? 1 : 0;
  }
  return value;
}

std::string generatePublicId(int length) {
  static const char alphabet[] = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
  static bool seeded = false;
  if (!seeded) {
    std::srand(static_cast<unsigned int>(std::time(nullptr)));
    seeded = true;
  }

  int target = length > 0 ? length : 26;
  std::string out;
  out.reserve(static_cast<std::size_t>(target));
  for (int index = 0; index < target; ++index) {
    out += alphabet[std::rand() % 32];
  }
  return out;
}

std::string nowIsoString() {
  auto now = std::chrono::system_clock::now();
  std::time_t timeValue = std::chrono::system_clock::to_time_t(now);
  std::tm tmValue {};
  gmtime_r(&timeValue, &tmValue);
  char buffer[32];
  std::strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &tmValue);
  return buffer;
}

struct RequestContext {
  std::optional<long long> tenantId;
  std::optional<long long> userId;
};

RequestContext parseContext(const json &payload) {
  RequestContext context;
  if (!payload.is_object()) {
    return context;
  }

  context.tenantId = parseIntegerLike(payload.contains("tenantId") ? payload["tenantId"] : json(nullptr));
  context.userId = parseIntegerLike(payload.contains("userId") ? payload["userId"] : json(nullptr));
  return context;
}

json normalizeValueForColumn(const ColumnMeta &column, const json &value) {
  json scalar = unwrapInputValue(value);
  if (scalar.is_null()) {
    return nullptr;
  }

  if (scalar.is_string() && trim(scalar.get<std::string>()).empty()) {
    return nullptr;
  }

  std::string type = column.data_type;
  if (type == "bit") {
    std::optional<bool> parsed = parseBooleanLike(scalar);
    return parsed.has_value() ? json(*parsed) : json(nullptr);
  }
  if (type == "bigint" || type == "int" || type == "integer" || type == "smallint") {
    std::optional<long long> parsed = parseIntegerLike(scalar);
    return parsed.has_value() ? json(*parsed) : json(nullptr);
  }
  if (type == "decimal" || type == "numeric") {
    try {
      if (scalar.is_number()) {
        return scalar;
      }
      return json(std::stod(stringifyValue(scalar)));
    } catch (...) {
      return nullptr;
    }
  }
  if (type == "json" || type == "jsonb") {
    if (scalar.is_string()) {
      try {
        return json::parse(scalar.get<std::string>());
      } catch (...) {
        return scalar.get<std::string>();
      }
    }
    return scalar;
  }
  if (type == "date" || type == "datetime" || type == "datetime2") {
    return stringifyValue(scalar);
  }
  return scalar.is_string() ? scalar.get<std::string>() : stringifyValue(scalar);
}

json normalizeRowInput(const ObjectMeta &object, const json &row, const RequestContext &context) {
  json normalized = json::object();
  std::map<std::string, std::string> aliasMap = buildAliasMap(object);

  if (!row.is_object()) {
    return normalized;
  }

  for (auto it = row.begin(); it != row.end(); ++it) {
    auto aliasIt = aliasMap.find(toLower(trim(it.key())));
    if (aliasIt == aliasMap.end()) {
      continue;
    }
    const ColumnMeta *column = findColumn(object, aliasIt->second);
    if (!column) {
      continue;
    }
    normalized[column->name] = normalizeValueForColumn(*column, it.value());
  }

  bool hasId = normalized.contains("id") && !normalized["id"].is_null() &&
               !(normalized["id"].is_string() && trim(normalized["id"].get<std::string>()).empty());

  if (!hasId && findColumn(object, "public_id") && (!normalized.contains("public_id") || normalized["public_id"].is_null())) {
    const ColumnMeta *publicColumn = findColumn(object, "public_id");
    normalized["public_id"] = generatePublicId(publicColumn ? publicColumn->max_length : 26);
  }

  if (!hasId && context.tenantId.has_value() && findColumn(object, "tenant_id") &&
      (!normalized.contains("tenant_id") || normalized["tenant_id"].is_null())) {
    normalized["tenant_id"] = *context.tenantId;
  }

  if (!hasId && findColumn(object, "created_at") && (!normalized.contains("created_at") || normalized["created_at"].is_null())) {
    normalized["created_at"] = nowIsoString();
  }
  if (hasId && findColumn(object, "updated_at")) {
    normalized["updated_at"] = nowIsoString();
  }

  if (!hasId && context.userId.has_value() && findColumn(object, "created_by") &&
      (!normalized.contains("created_by") || normalized["created_by"].is_null())) {
    normalized["created_by"] = *context.userId;
  }
  if (hasId && context.userId.has_value() && findColumn(object, "updated_by")) {
    normalized["updated_by"] = *context.userId;
  }

  return normalized;
}

class PgRuntime {
public:
  PgRuntime() = default;

  ~PgRuntime() {
    if (connection_) {
      PQfinish(connection_);
      connection_ = nullptr;
    }
  }

  bool connect() {
    if (connection_ && PQstatus(connection_) == CONNECTION_OK) {
      return true;
    }

    std::string connString = buildConnectionString();
    if (connection_) {
      PQfinish(connection_);
      connection_ = nullptr;
    }

    connection_ = PQconnectdb(connString.c_str());
    return PQstatus(connection_) == CONNECTION_OK;
  }

  std::string lastError() const {
    return connection_ ? PQerrorMessage(connection_) : "Database connection is not initialized";
  }

  json health() {
    if (!connect()) {
      return {
          {"status", "error"},
          {"database", false},
          {"error", lastError()}};
    }

    PGresult *result = PQexec(connection_, "SELECT 1");
    bool ok = PQresultStatus(result) == PGRES_TUPLES_OK;
    if (result) {
      PQclear(result);
    }
    return {
        {"status", ok ? "ok" : "error"},
        {"database", ok},
        {"driver", "libpq"}};
  }

  json handleRead(const json &payload) {
    ObjectMeta object = parseObjectMeta(payload.at("object"));
    json options = payload.value("options", json::object());
    RequestContext context = parseContext(payload.value("context", json::object()));

    std::string requestedColumns = jsonString(options, "columns");
    if (requestedColumns.empty()) {
      requestedColumns = jsonString(options, "Columns");
    }
    if (requestedColumns.empty()) {
      requestedColumns = jsonString(options, "cols");
    }
    if (requestedColumns.empty()) {
      requestedColumns = jsonString(options, "Cols");
    }

    std::vector<const ColumnMeta *> selectedColumns = normalizeSelectedColumns(object, requestedColumns);
    if (selectedColumns.empty()) {
      for (const ColumnMeta &column : object.columns) {
        selectedColumns.push_back(&column);
      }
    }

    std::vector<std::optional<std::string>> whereValues;
    std::string whereSql = buildWhereClause(object, payload.value("filters", payload.value("Filters", json::array())), whereValues, context);
    std::vector<std::string> orderTerms = normalizeOrderTerms(object, options.value("order", options.value("Order", "")));
    int limit = jsonIntOrString(options, "top", jsonIntOrString(options, "Top", 100));
    int page = jsonIntOrString(options, "page", jsonIntOrString(options, "Page", 1));
    if (limit <= 0) limit = 100;
    if (page <= 0) page = 1;
    int offset = (page - 1) * limit;

    std::string selectSql;
    {
      std::vector<std::string> selectParts;
      for (const ColumnMeta *column : selectedColumns) {
        selectParts.push_back("t." + quoteIdent(column->name) + " AS " + quoteIdent(column->name));
      }
      selectSql = join(selectParts, ", ");
    }

    std::string orderSql;
    if (!orderTerms.empty()) {
      orderSql = " ORDER BY " + join(orderTerms, ", ");
    } else if (findColumn(object, "id")) {
      orderSql = " ORDER BY t.\"id\" DESC";
    }

    std::vector<std::optional<std::string>> selectValues = whereValues;
    selectValues.emplace_back(std::to_string(limit));
    selectValues.emplace_back(std::to_string(offset));

    std::string sql = "SELECT " + selectSql + " FROM " + quoteIdent(object.name) + " t" + whereSql + orderSql +
                      " LIMIT $" + std::to_string(static_cast<int>(selectValues.size() - 1)) +
                      " OFFSET $" + std::to_string(static_cast<int>(selectValues.size()));
    std::string countSql = "SELECT COUNT(*)::int AS total FROM " + quoteIdent(object.name) + " t" + whereSql;

    PGresult *rowsResult = execParams(sql, selectValues);
    ensureStatus(rowsResult, PGRES_TUPLES_OK, "Read query failed");

    PGresult *countResult = execParams(countSql, whereValues);
    ensureStatus(countResult, PGRES_TUPLES_OK, "Read count failed");

    std::map<std::string, std::map<std::string, std::string>> references = loadReferenceMaps(object, selectedColumns, rowsResult);
    json data = normalizeOutputRows(selectedColumns, rowsResult, references);
    int total = 0;
    if (PQntuples(countResult) > 0) {
      total = std::atoi(PQgetvalue(countResult, 0, 0));
    }

    PQclear(rowsResult);
    PQclear(countResult);

    json selectedColumnsJson = selectedColumnMetaJson(payload.at("object").at("columns"), selectedColumns);

    json result = {
        {"data", data},
        {"columns", selectedColumnsJson},
        {"count", total},
        {"top", limit},
        {"page", page},
        {"allcolumns", allColumnNames(selectedColumns)},
        {"table_childs", payload.at("object").value("table_childs", json::array())},
        {"request_info",
         {
             {"action", "read"},
             {"name", object.name},
             {"filters", payload.value("filters", payload.value("Filters", json::array()))},
             {"params", payload.value("params", payload.value("Params", nullptr))},
             {"options", options},
         }}};

    bool dataOnly = false;
    if (options.contains("DataOnly")) {
      dataOnly = options["DataOnly"].is_boolean() ? options["DataOnly"].get<bool>()
                                                  : toLower(stringifyValue(options["DataOnly"])) == "true";
    }
    if (options.contains("dataOnly")) {
      dataOnly = dataOnly || (options["dataOnly"].is_boolean() ? options["dataOnly"].get<bool>()
                                                                : toLower(stringifyValue(options["dataOnly"])) == "true");
    }

    return dataOnly ? data : result;
  }

  json handleSave(const json &payload) {
    RequestContext context = parseContext(payload.value("context", json::object()));
    json results = json::array();

    if (!payload.contains("entries") || !payload["entries"].is_array()) {
      return results;
    }

    for (const json &entry : payload["entries"]) {
      ObjectMeta object = parseObjectMeta(entry.at("object"));
      const ColumnMeta *pkColumn = getPrimaryKey(object);
      if (!pkColumn) {
        throw std::runtime_error("Primary key is missing for " + object.name);
      }

      json rowsValue = entry.value("data", json::array());
      if (!rowsValue.is_array()) {
        rowsValue = json::array();
      }

      json normalizedRows = json::array();
      for (const json &row : rowsValue) {
        normalizedRows.push_back(normalizeRowInput(object, row, context));
      }

      std::vector<std::string> requested;
      if (entry.contains("columns") && entry["columns"].is_array()) {
        for (const json &item : entry["columns"]) {
          std::string name = item.is_object() ? item.value("name", "") : stringifyValue(item);
          if (!name.empty()) {
            requested.push_back(name);
          }
        }
      }

      std::vector<ColumnMeta> writableColumns = buildWritableColumns(object, requested, normalizedRows);

      std::vector<ColumnMeta> dataColumns;
      dataColumns.push_back(*pkColumn);
      for (const ColumnMeta &column : writableColumns) {
        if (column.name != pkColumn->name) {
          dataColumns.push_back(column);
        }
      }

      std::string recordsetSql = buildRecordsetDefinition(dataColumns);
      std::string updateSql = buildUpdateSql(object, *pkColumn, dataColumns);
      std::string insertSql = buildInsertSql(object, *pkColumn, dataColumns);

      int updateCount = 0;
      int insertCount = 0;
      std::optional<std::string> payloadJson = normalizedRows.dump();

      execSimple("BEGIN");
      try {
        if (!updateSql.empty()) {
          PGresult *updateResult = execParams(updateSql, {payloadJson});
          ensureStatus(updateResult, PGRES_COMMAND_OK, "Update failed");
          updateCount = std::atoi(PQcmdTuples(updateResult));
          PQclear(updateResult);
        }

        if (!insertSql.empty()) {
          PGresult *insertResult = execParams(insertSql, {payloadJson});
          ensureStatus(insertResult, PGRES_TUPLES_OK, "Insert failed");
          if (PQntuples(insertResult) > 0) {
            insertCount = std::atoi(PQgetvalue(insertResult, 0, 0));
          }
          PQclear(insertResult);
        }
        execSimple("COMMIT");
      } catch (...) {
        execSimple("ROLLBACK");
        throw;
      }

      results.push_back({
          {"name", object.name},
          {"insertResult", std::to_string(insertCount)},
          {"updateResult", std::to_string(updateCount)},
          {"countInsertResult", insertCount},
          {"countUpdateResult", updateCount},
          {"insertSQL", collapseSpaces(insertSql)},
          {"updateSQL", collapseSpaces(updateSql)},
          {"accepted", true},
      });
    }

    return results;
  }

  json handleDelete(const json &payload) {
    ObjectMeta object = parseObjectMeta(payload.at("object"));
    RequestContext context = parseContext(payload.value("context", json::object()));
    const ColumnMeta *pkColumn = getPrimaryKey(object);
    if (!pkColumn) {
      throw std::runtime_error("Primary key is missing for " + object.name);
    }

    json rowid = payload.contains("rowid") ? payload["rowid"] : json(nullptr);
    json normalizedId = normalizeValueForColumn(*pkColumn, rowid);
    std::vector<std::optional<std::string>> values;
    values.emplace_back(normalizedId.is_null() ? std::optional<std::string>() : std::optional<std::string>(stringifyValue(normalizedId)));

    std::string sql = "DELETE FROM " + quoteIdent(object.name) + " WHERE " + quoteIdent(pkColumn->name) + " = $1";
    if (findColumn(object, "tenant_id") && context.tenantId.has_value()) {
      values.emplace_back(std::to_string(*context.tenantId));
      sql += " AND \"tenant_id\" = $2";
    }

    PGresult *result = execParams(sql, values);
    ensureStatus(result, PGRES_COMMAND_OK, "Delete failed");
    int affected = std::atoi(PQcmdTuples(result));
    PQclear(result);

    return {
        {"ok", true},
        {"deleted", affected > 0},
        {"contract_only", false},
        {"name", object.name},
        {"rowid", rowid}};
  }

  json handleRoutine(const json &payload) {
    std::string kind = toLower(payload.value("kind", "fun"));
    std::string name = payload.value("name", "");
    json paramsJson = payload.value("params", json::array());
    if (!paramsJson.is_array()) {
      paramsJson = json::array();
    }

    std::vector<json> params;
    for (const json &value : paramsJson) {
      params.push_back(value);
    }

    json routine = pickRoutine(name, kind, static_cast<int>(params.size()));
    if (routine.is_null()) {
      throw std::runtime_error("Unknown " + kind + " routine or wrong parameters count: " + name);
    }

    auto startedAt = std::chrono::steady_clock::now();
    json args = routine.value("inputArgs", json::array());
    std::vector<std::optional<std::string>> values;
    for (std::size_t index = 0; index < params.size(); ++index) {
      json value = normalizeRoutineParamValue(params[index], args.at(index));
      values.emplace_back(value.is_null() ? std::optional<std::string>() : std::optional<std::string>(stringifyValue(value)));
    }

    std::string sql;
    PGresult *result = nullptr;
    std::string prokind = routine.value("prokind", "f");
    bool isSetReturning = routine.value("setReturning", false);

    if (prokind == "p") {
      sql = buildRoutineSql(routine, static_cast<int>(values.size()), "call");
      result = execParams(sql, values);
      ensureStatus(result, PGRES_COMMAND_OK, "Procedure call failed");
      int affected = std::atoi(PQcmdTuples(result));
      PQclear(result);
      return buildRoutineResponse(json::array(), sql, paramsJson, startedAt, {
          {"RecordsAffected", affected},
          {"routine_kind", "proc"},
          {"routine_name", routine.value("routine_name", name)},
          {"routine_schema", routine.value("schema_name", "public")},
      });
    }

    sql = buildRoutineSql(routine, static_cast<int>(values.size()), isSetReturning ? "select_rows" : "select_scalar");
    result = execParams(sql, values);
    ensureStatus(result, PGRES_TUPLES_OK, "Function execution failed");

    if (!isSetReturning) {
      json scalar = nullptr;
      if (PQntuples(result) > 0 && PQnfields(result) > 0 && !PQgetisnull(result, 0, 0)) {
        scalar = parseFieldValue(PQgetvalue(result, 0, 0), PQftype(result, 0));
      }
      int affected = PQntuples(result) > 0 ? 1 : 0;
      PQclear(result);
      return buildRoutineResponse(
          scalar.is_null() ? json::array() : json::array({{{"value", scalar}}}),
          sql,
          paramsJson,
          startedAt,
          {
              {"RecordsAffected", affected},
              {"scalar", scalar},
              {"routine_kind", kind},
              {"routine_name", routine.value("routine_name", name)},
              {"routine_schema", routine.value("schema_name", "public")},
          });
    }

    json rows = json::array();
    int rowCount = PQntuples(result);
    int fieldCount = PQnfields(result);
    for (int rowIndex = 0; rowIndex < rowCount; ++rowIndex) {
      json row = json::object();
      for (int fieldIndex = 0; fieldIndex < fieldCount; ++fieldIndex) {
        std::string fieldName = PQfname(result, fieldIndex);
        json value = PQgetisnull(result, rowIndex, fieldIndex)
                         ? json(nullptr)
                         : parseFieldValue(PQgetvalue(result, rowIndex, fieldIndex), PQftype(result, fieldIndex));
        row[fieldName] = value;
        if (fieldName == "id") {
          row["ID"] = value;
        }
      }
      rows.push_back(row);
    }
    int affected = rowCount;
    PQclear(result);
    return buildRoutineResponse(
        rows,
        sql,
        paramsJson,
        startedAt,
        {
            {"RecordsAffected", affected},
            {"routine_kind", kind},
            {"routine_name", routine.value("routine_name", name)},
            {"routine_schema", routine.value("schema_name", "public")},
        });
  }

private:
  PGconn *connection_ = nullptr;

  std::string buildConnectionString() const {
    const char *databaseUrl = std::getenv("DATABASE_URL");
    if (databaseUrl && *databaseUrl) {
      return databaseUrl;
    }

    std::ostringstream stream;
    stream << "host=" << envOrDefault("PGHOST", "127.0.0.1")
           << " port=" << envOrDefault("PGPORT", "5432")
           << " dbname=" << envOrDefault("PGDATABASE", "ai_auto")
           << " user=" << envOrDefault("PGUSER", "ai_auto")
           << " password=" << envOrDefault("PGPASSWORD", "")
           << " client_encoding=UTF8";
    return stream.str();
  }

  void execSimple(const std::string &sql) {
    PGresult *result = PQexec(connection_, sql.c_str());
    ExecStatusType status = PQresultStatus(result);
    if (status != PGRES_COMMAND_OK && status != PGRES_TUPLES_OK) {
      std::string error = PQerrorMessage(connection_);
      PQclear(result);
      throw std::runtime_error(error);
    }
    PQclear(result);
  }

  PGresult *execParams(const std::string &sql, const std::vector<std::optional<std::string>> &values) {
    if (!connect()) {
      throw std::runtime_error(lastError());
    }

    std::vector<const char *> rawValues;
    rawValues.reserve(values.size());
    for (const std::optional<std::string> &value : values) {
      rawValues.push_back(value.has_value() ? value->c_str() : nullptr);
    }

    return PQexecParams(connection_,
                        sql.c_str(),
                        static_cast<int>(values.size()),
                        nullptr,
                        rawValues.empty() ? nullptr : rawValues.data(),
                        nullptr,
                        nullptr,
                        0);
  }

  void ensureStatus(PGresult *result, ExecStatusType expected, const std::string &prefix) {
    ExecStatusType actual = PQresultStatus(result);
    if (actual != expected) {
      std::string error = prefix + ": " + PQerrorMessage(connection_);
      PQclear(result);
      throw std::runtime_error(error);
    }
  }

  std::vector<const ColumnMeta *> normalizeSelectedColumns(const ObjectMeta &object, const std::string &columnsCsv) {
    std::vector<const ColumnMeta *> selected;
    if (trim(columnsCsv).empty()) {
      return selected;
    }

    std::vector<std::string> names;
    std::stringstream stream(columnsCsv);
    std::string part;
    while (std::getline(stream, part, ',')) {
      std::optional<std::string> resolved = resolveColumnName(object, part);
      if (resolved.has_value()) {
        names.push_back(*resolved);
      }
    }

    for (const std::string &name : names) {
      const ColumnMeta *column = findColumn(object, name);
      if (column) {
        selected.push_back(column);
      }
    }

    const ColumnMeta *pkColumn = getPrimaryKey(object);
    if (pkColumn) {
      bool hasPk = false;
      for (const ColumnMeta *column : selected) {
        if (column && column->name == pkColumn->name) {
          hasPk = true;
          break;
        }
      }
      if (!hasPk) {
        selected.insert(selected.begin(), pkColumn);
      }
    }
    return selected;
  }

  std::vector<std::string> normalizeOrderTerms(const ObjectMeta &object, const std::string &rawOrder) {
    std::vector<std::string> terms;
    std::stringstream stream(rawOrder);
    std::string item;
    while (std::getline(stream, item, ',')) {
      item = trim(item);
      if (item.empty()) {
        continue;
      }
      std::stringstream itemStream(item);
      std::string name;
      std::string direction;
      itemStream >> name >> direction;
      std::optional<std::string> resolved = resolveColumnName(object, name);
      if (!resolved.has_value()) {
        continue;
      }
      std::string dir = toLower(direction) == "desc" ? "DESC" : "ASC";
      terms.push_back(quoteIdent(*resolved) + " " + dir);
    }
    return terms;
  }

  std::string buildWhereClause(const ObjectMeta &object,
                               const json &filtersValue,
                               std::vector<std::optional<std::string>> &values,
                               const RequestContext &context) {
    json filters = filtersValue;
    if (filters.is_string()) {
      try {
        filters = json::parse(filters.get<std::string>());
      } catch (...) {
        filters = json::array();
      }
    }
    if (!filters.is_array()) {
      filters = json::array();
    }

    struct SqlPart {
      std::string logic;
      std::string sql;
    };
    std::vector<SqlPart> parts;
    bool hasTenantFilter = false;

    for (const json &filter : filters) {
      if (!filter.is_object()) {
        continue;
      }
      std::optional<std::string> resolvedName = resolveColumnName(object, filter.value("column_name", ""));
      if (!resolvedName.has_value()) {
        continue;
      }
      const ColumnMeta *column = findColumn(object, *resolvedName);
      if (!column) {
        continue;
      }

      if (column->name == "tenant_id") {
        hasTenantFilter = true;
      }

      std::string logic = toLower(filter.value("logic", filter.value("cond_type", "and"))) == "or" ? "OR" : "AND";
      std::string sql = filter.value("column_name_type", "") == "name" && !column->referenced_table.empty()
                            ? buildReferenceFilterSql(*column, filter, values)
                            : buildDirectFilterSql(*column, filter, values);
      if (!sql.empty()) {
        parts.push_back({logic, sql});
      }
    }

    if (!hasTenantFilter && context.tenantId.has_value() && findColumn(object, "tenant_id")) {
      values.emplace_back(std::to_string(*context.tenantId));
      parts.push_back({"AND", "t.\"tenant_id\" = $" + std::to_string(static_cast<int>(values.size()))});
    }

    if (parts.empty()) {
      return "";
    }

    std::string out = " WHERE ";
    for (std::size_t index = 0; index < parts.size(); ++index) {
      if (index) {
        out += " " + parts[index].logic + " ";
      }
      out += "(" + parts[index].sql + ")";
    }
    return out;
  }

  std::string buildDirectFilterSql(const ColumnMeta &column,
                                   const json &filter,
                                   std::vector<std::optional<std::string>> &values) {
    std::string fieldSql = "t." + quoteIdent(column.name);
    std::string cond = toLower(filter.value("cond", "="));
    json rawValue = filter.contains("value") ? filter["value"] : json(nullptr);

    if (cond == "is null") {
      return fieldSql + " IS NULL";
    }
    if (cond == "is not null") {
      return fieldSql + " IS NOT NULL";
    }
    if (cond == "between") {
      json parts = rawValue;
      if (!parts.is_array() && parts.is_string()) {
        std::string text = rawValue.get<std::string>();
        std::regex pattern("\\s+and\\s+", std::regex::icase);
        std::sregex_token_iterator iterator(text.begin(), text.end(), pattern, -1);
        std::sregex_token_iterator end;
        json parsed = json::array();
        for (; iterator != end; ++iterator) {
          parsed.push_back(trim(iterator->str()));
        }
        parts = parsed;
      }
      if (!parts.is_array() || parts.size() < 2) {
        return "";
      }
      json left = normalizeValueForColumn(column, parts.at(0));
      json right = normalizeValueForColumn(column, parts.at(1));
      values.emplace_back(left.is_null() ? std::optional<std::string>() : std::optional<std::string>(stringifyValue(left)));
      values.emplace_back(right.is_null() ? std::optional<std::string>() : std::optional<std::string>(stringifyValue(right)));
      return fieldSql + " BETWEEN $" + std::to_string(static_cast<int>(values.size() - 1)) +
             " AND $" + std::to_string(static_cast<int>(values.size()));
    }
    if (cond == "in" || cond == "not in") {
      std::vector<std::string> items;
      if (rawValue.is_array()) {
        for (const json &item : rawValue) {
          items.push_back(stringifyValue(normalizeValueForColumn(column, item)));
        }
      } else if (rawValue.is_string()) {
        std::stringstream stream(rawValue.get<std::string>());
        std::string item;
        while (std::getline(stream, item, ',')) {
          items.push_back(trim(item));
        }
      }
      if (items.empty()) {
        return "";
      }
      std::vector<std::string> placeholders;
      for (const std::string &item : items) {
        values.emplace_back(item);
        placeholders.push_back("$" + std::to_string(static_cast<int>(values.size())));
      }
      return fieldSql + " " + (cond == "not in" ? "NOT IN" : "IN") + " (" + join(placeholders, ", ") + ")";
    }
    if (cond == "like" || cond == "contains") {
      values.emplace_back("%" + escapeLike(stringifyValue(rawValue)) + "%");
      return fieldSql + "::text ILIKE $" + std::to_string(static_cast<int>(values.size())) + " ESCAPE '\\'";
    }
    if (cond == "startswith") {
      values.emplace_back(escapeLike(stringifyValue(rawValue)) + "%");
      return fieldSql + "::text ILIKE $" + std::to_string(static_cast<int>(values.size())) + " ESCAPE '\\'";
    }
    if (cond == "endswith") {
      values.emplace_back("%" + escapeLike(stringifyValue(rawValue)));
      return fieldSql + "::text ILIKE $" + std::to_string(static_cast<int>(values.size())) + " ESCAPE '\\'";
    }

    static const std::map<std::string, std::string> ops = {
        {"=", "="},
        {"==", "="},
        {"!=", "<>"},
        {"<>", "<>"},
        {">", ">"},
        {">=", ">="},
        {"<", "<"},
        {"<=", "<="},
    };

    auto op = ops.find(cond);
    if (op == ops.end()) {
      return "";
    }

    json normalized = normalizeValueForColumn(column, rawValue);
    values.emplace_back(normalized.is_null() ? std::optional<std::string>() : std::optional<std::string>(stringifyValue(normalized)));
    return fieldSql + " " + op->second + " $" + std::to_string(static_cast<int>(values.size()));
  }

  std::string buildReferenceFilterSql(const ColumnMeta &column,
                                      const json &filter,
                                      std::vector<std::optional<std::string>> &values) {
    if (column.referenced_table.empty()) {
      return "";
    }

    std::vector<std::string> searchColumns;
    std::stringstream stream(column.search_columns.empty() ? "name" : column.search_columns);
    std::string item;
    while (std::getline(stream, item, ',')) {
      item = trim(item);
      if (!item.empty()) {
        searchColumns.push_back(item);
      }
    }
    if (searchColumns.empty()) {
      return "";
    }

    std::string refColumn = trim(column.referenced_column_name.empty() ? "id" : column.referenced_column_name);
    std::string cond = toLower(filter.value("cond", "like"));
    json rawValue = filter.contains("value") ? filter["value"] : json(nullptr);

    std::vector<std::string> clauses;
    for (const std::string &searchColumn : searchColumns) {
      std::string searchSql = "r." + quoteIdent(searchColumn) + "::text";
      if (cond == "like" || cond == "contains") {
        values.emplace_back("%" + escapeLike(stringifyValue(rawValue)) + "%");
        clauses.push_back(searchSql + " ILIKE $" + std::to_string(static_cast<int>(values.size())) + " ESCAPE '\\'");
      } else {
        values.emplace_back(stringifyValue(rawValue));
        std::string op = (cond == "!=" || cond == "<>") ? "<>" : "=";
        clauses.push_back(searchSql + " " + op + " $" + std::to_string(static_cast<int>(values.size())));
      }
    }

    if (clauses.empty()) {
      return "";
    }

    return "EXISTS (SELECT 1 FROM " + quoteIdent(column.referenced_table) + " r WHERE r." +
           quoteIdent(refColumn) + " = t." + quoteIdent(column.name) + " AND (" + join(clauses, " OR ") + "))";
  }

  std::map<std::string, std::map<std::string, std::string>>
  loadReferenceMaps(const ObjectMeta &,
                    const std::vector<const ColumnMeta *> &selectedColumns,
                    PGresult *rowsResult) {
    std::map<std::string, std::map<std::string, std::string>> output;

    for (const ColumnMeta *column : selectedColumns) {
      if (!column->isreferences || column->referenced_table.empty()) {
        continue;
      }

      std::vector<std::string> ids;
      std::map<std::string, bool> seen;
      int rowCount = PQntuples(rowsResult);
      int fieldIndex = PQfnumber(rowsResult, column->name.c_str());
      if (fieldIndex < 0) {
        continue;
      }
      for (int rowIndex = 0; rowIndex < rowCount; ++rowIndex) {
        if (PQgetisnull(rowsResult, rowIndex, fieldIndex)) {
          continue;
        }
        std::string value = PQgetvalue(rowsResult, rowIndex, fieldIndex);
        if (!value.empty() && !seen[value]) {
          ids.push_back(value);
          seen[value] = true;
        }
      }

      if (ids.empty()) {
        continue;
      }

      std::vector<std::string> searchColumns;
      std::stringstream stream(column->search_columns.empty() ? "name" : column->search_columns);
      std::string item;
      while (std::getline(stream, item, ',')) {
        item = trim(item);
        if (!item.empty()) {
          searchColumns.push_back(item);
        }
      }
      if (searchColumns.empty()) {
        continue;
      }

      std::vector<std::string> selectParts = {" " + quoteIdent(column->referenced_column_name.empty() ? "id" : column->referenced_column_name) + "::text AS \"__id\" "};
      for (const std::string &searchColumn : searchColumns) {
        selectParts.push_back(quoteIdent(searchColumn));
      }
      std::string sql = "SELECT " + join(selectParts, ", ") + " FROM " + quoteIdent(column->referenced_table) +
                        " WHERE " + quoteIdent(column->referenced_column_name.empty() ? "id" : column->referenced_column_name) +
                        "::text = ANY($1::text[])";

      PGresult *result = execParams(sql, {jsonToPgArray(ids)});
      ensureStatus(result, PGRES_TUPLES_OK, "Reference lookup failed");

      std::map<std::string, std::string> map;
      int resultRows = PQntuples(result);
      for (int rowIndex = 0; rowIndex < resultRows; ++rowIndex) {
        std::vector<std::string> displayParts;
        for (std::size_t searchIndex = 0; searchIndex < searchColumns.size(); ++searchIndex) {
          int searchField = static_cast<int>(searchIndex + 1);
          if (!PQgetisnull(result, rowIndex, searchField)) {
            std::string value = trim(PQgetvalue(result, rowIndex, searchField));
            if (!value.empty()) {
              displayParts.push_back(value);
            }
          }
        }
        std::string id = PQgetvalue(result, rowIndex, 0);
        map[id] = displayParts.empty() ? id : join(displayParts, " - ");
      }

      PQclear(result);
      output[column->name] = map;
    }

    return output;
  }

  json normalizeOutputRows(const std::vector<const ColumnMeta *> &selectedColumns,
                           PGresult *rowsResult,
                           const std::map<std::string, std::map<std::string, std::string>> &references) {
    json rows = json::array();
    int rowCount = PQntuples(rowsResult);
    for (int rowIndex = 0; rowIndex < rowCount; ++rowIndex) {
      json row = json::object();
      for (const ColumnMeta *column : selectedColumns) {
        int fieldIndex = PQfnumber(rowsResult, column->name.c_str());
        if (fieldIndex < 0) {
          continue;
        }
        if (column->isreferences && !column->referenced_table.empty()) {
          if (PQgetisnull(rowsResult, rowIndex, fieldIndex)) {
            row[column->name] = nullptr;
          } else {
            std::string value = PQgetvalue(rowsResult, rowIndex, fieldIndex);
            auto refMap = references.find(column->name);
            std::string display = value;
            if (refMap != references.end()) {
              auto found = refMap->second.find(value);
              if (found != refMap->second.end()) {
                display = found->second;
              }
            }
            row[column->name] = {
                {"id", value},
                {"value", display}};
          }
          continue;
        }

        if (PQgetisnull(rowsResult, rowIndex, fieldIndex)) {
          if (column->name == "id") {
            row["ID"] = nullptr;
          } else {
            row[column->name] = nullptr;
          }
          continue;
        }

        std::string raw = PQgetvalue(rowsResult, rowIndex, fieldIndex);
        json value = formatCellForOutput(*column, raw);
        if (column->name == "id") {
          row["ID"] = value;
        } else {
          row[column->name] = value;
        }
      }
      rows.push_back(row);
    }
    return rows;
  }

  std::string allColumnNames(const std::vector<const ColumnMeta *> &selectedColumns) {
    std::vector<std::string> names;
    for (const ColumnMeta *column : selectedColumns) {
      names.push_back(column->name);
    }
    return join(names, ",");
  }

  json selectedColumnMetaJson(const json &allColumnsJson, const std::vector<const ColumnMeta *> &selectedColumns) {
    if (!allColumnsJson.is_array()) {
      return json::array();
    }

    std::map<std::string, bool> selectedNames;
    for (const ColumnMeta *column : selectedColumns) {
      if (!column) {
        continue;
      }
      selectedNames[toLower(column->name)] = true;
    }

    json filtered = json::array();
    for (const json &column : allColumnsJson) {
      std::string name = toLower(jsonString(column, "name"));
      if (!name.empty() && selectedNames.find(name) != selectedNames.end()) {
        json normalized = column;
        if (name == "id") {
          normalized["is_nullable"] = true;
          normalized["is_edit_show"] = false;
        }
        filtered.push_back(normalized);
      }
    }
    return filtered;
  }

  std::vector<ColumnMeta> buildWritableColumns(const ObjectMeta &object,
                                               const std::vector<std::string> &requested,
                                               const json &normalizedRows) {
    std::map<std::string, bool> requestedSet;
    for (const std::string &name : requested) {
      std::optional<std::string> resolved = resolveColumnName(object, name);
      if (resolved.has_value()) {
        requestedSet[*resolved] = true;
      }
    }

    std::vector<ColumnMeta> output;
    for (const ColumnMeta &column : object.columns) {
      if (column.is_identity && column.name == "id") {
        continue;
      }
      bool present = false;
      for (const json &row : normalizedRows) {
        if (row.is_object() && row.contains(column.name)) {
          present = true;
          break;
        }
      }
      if (!requestedSet.empty() && !requestedSet[column.name] && !present) {
        continue;
      }
      if (present) {
        output.push_back(column);
      }
    }
    return output;
  }

  std::string buildRecordsetDefinition(const std::vector<ColumnMeta> &columns) {
    std::vector<std::string> parts;
    for (const ColumnMeta &column : columns) {
      parts.push_back(quoteIdent(column.name) + " " + getRecordsetType(column));
    }
    return join(parts, ", ");
  }

  std::string buildUpdateSql(const ObjectMeta &object,
                             const ColumnMeta &pkColumn,
                             const std::vector<ColumnMeta> &dataColumns) {
    std::vector<std::string> assignments;
    for (const ColumnMeta &column : dataColumns) {
      if (column.name == pkColumn.name || column.name == "created_at" || column.name == "created_by") {
        continue;
      }
      assignments.push_back(quoteIdent(column.name) + " = s." + quoteIdent(column.name));
    }
    if (assignments.empty()) {
      return "";
    }

    return "WITH source AS ( SELECT * FROM jsonb_to_recordset($1::jsonb) AS s(" + buildRecordsetDefinition(dataColumns) +
           ") ) UPDATE " + quoteIdent(object.name) + " AS t SET " + join(assignments, ", ") +
           " FROM source AS s WHERE s." + quoteIdent(pkColumn.name) + " IS NOT NULL AND t." + quoteIdent(pkColumn.name) +
           " = s." + quoteIdent(pkColumn.name);
  }

  std::string buildInsertSql(const ObjectMeta &object,
                             const ColumnMeta &pkColumn,
                             const std::vector<ColumnMeta> &dataColumns) {
    std::vector<ColumnMeta> insertColumns;
    for (const ColumnMeta &column : dataColumns) {
      if (column.name != pkColumn.name) {
        insertColumns.push_back(column);
      }
    }
    if (insertColumns.empty()) {
      return "";
    }

    std::vector<ColumnMeta> withIdColumns;
    withIdColumns.push_back(pkColumn);
    withIdColumns.insert(withIdColumns.end(), insertColumns.begin(), insertColumns.end());

    std::vector<std::string> insertColumnNames;
    std::vector<std::string> insertSelectNames;
    for (const ColumnMeta &column : insertColumns) {
      insertColumnNames.push_back(quoteIdent(column.name));
      insertSelectNames.push_back("s." + quoteIdent(column.name));
    }

    std::vector<std::string> withIdColumnNames;
    std::vector<std::string> withIdSelectNames;
    for (const ColumnMeta &column : withIdColumns) {
      withIdColumnNames.push_back(quoteIdent(column.name));
      withIdSelectNames.push_back("s." + quoteIdent(column.name));
    }

    std::string overriding = pkColumn.is_identity ? " OVERRIDING SYSTEM VALUE" : "";

    return "WITH source AS ( SELECT * FROM jsonb_to_recordset($1::jsonb) AS s(" + buildRecordsetDefinition(dataColumns) +
           ") ), inserted_with_id AS ( INSERT INTO " + quoteIdent(object.name) + " (" + join(withIdColumnNames, ", ") + ")" + overriding +
           " SELECT " + join(withIdSelectNames, ", ") + " FROM source AS s WHERE s." + quoteIdent(pkColumn.name) +
           " IS NOT NULL AND NOT EXISTS ( SELECT 1 FROM " + quoteIdent(object.name) + " AS t WHERE t." +
           quoteIdent(pkColumn.name) + " = s." + quoteIdent(pkColumn.name) +
           " ) RETURNING 1 ), inserted_without_id AS ( INSERT INTO " + quoteIdent(object.name) + " (" +
           join(insertColumnNames, ", ") + ") SELECT " + join(insertSelectNames, ", ") + " FROM source AS s WHERE s." +
           quoteIdent(pkColumn.name) + " IS NULL RETURNING 1 ) SELECT (SELECT COUNT(*)::int FROM inserted_with_id) + " +
           "(SELECT COUNT(*)::int FROM inserted_without_id) AS inserted_count";
  }

  std::string collapseSpaces(const std::string &value) {
    std::ostringstream stream;
    bool inSpace = false;
    for (char ch : value) {
      if (std::isspace(static_cast<unsigned char>(ch))) {
        if (!inSpace) {
          stream << ' ';
          inSpace = true;
        }
      } else {
        stream << ch;
        inSpace = false;
      }
    }
    return trim(stream.str());
  }

  json parseFieldValue(const char *text, Oid oid) {
    if (!text) {
      return nullptr;
    }

    std::string value = text;
    if (oid == 16) {
      return value == "t" || value == "true" || value == "1" ? 1 : 0;
    }
    if (oid == 20 || oid == 21 || oid == 23) {
      try {
        return std::stoll(value);
      } catch (...) {
        return value;
      }
    }
    if (oid == 700 || oid == 701 || oid == 1700) {
      try {
        return std::stod(value);
      } catch (...) {
        return value;
      }
    }
    if (oid == 114 || oid == 3802) {
      try {
        return json::parse(value);
      } catch (...) {
        return value;
      }
    }
    return value;
  }

  json pickRoutine(const std::string &name, const std::string &preferredKind, int paramCount) {
    std::string sql =
        "SELECT "
        "p.oid, "
        "n.nspname AS schema_name, "
        "p.proname AS routine_name, "
        "p.prokind, "
        "p.pronargdefaults AS default_count, "
        "pg_catalog.pg_get_function_result(p.oid) AS result_type, "
        "COALESCE(json_agg(json_build_object("
        "'position', a.ordinality, "
        "'type_name', pg_catalog.format_type(a.type_oid, NULL), "
        "'mode', COALESCE((p.proargmodes)[a.ordinality], 'i'), "
        "'name', COALESCE((p.proargnames)[a.ordinality], '')"
        ") ORDER BY a.ordinality) FILTER (WHERE a.type_oid IS NOT NULL), '[]'::json) AS args "
        "FROM pg_catalog.pg_proc p "
        "JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace "
        "LEFT JOIN LATERAL unnest(CASE "
        "WHEN p.proallargtypes IS NOT NULL THEN p.proallargtypes "
        "WHEN p.pronargs > 0 THEN string_to_array(p.proargtypes::text, ' ')::oid[] "
        "ELSE ARRAY[]::oid[] END) WITH ORDINALITY AS a(type_oid, ordinality) ON TRUE "
        "WHERE p.proname = $1 AND n.nspname NOT IN ('pg_catalog', 'information_schema') "
        "GROUP BY p.oid, n.nspname, p.proname, p.prokind, p.pronargdefaults "
        "ORDER BY CASE WHEN n.nspname = 'public' THEN 0 ELSE 1 END, p.oid";

    PGresult *result = execParams(sql, {name});
    ensureStatus(result, PGRES_TUPLES_OK, "Routine lookup failed");

    std::vector<json> candidates;
    int rowCount = PQntuples(result);
    for (int rowIndex = 0; rowIndex < rowCount; ++rowIndex) {
      json candidate;
      candidate["oid"] = std::atoi(PQgetvalue(result, rowIndex, 0));
      candidate["schema_name"] = PQgetvalue(result, rowIndex, 1);
      candidate["routine_name"] = PQgetvalue(result, rowIndex, 2);
      candidate["prokind"] = PQgetvalue(result, rowIndex, 3);
      candidate["default_count"] = std::atoi(PQgetvalue(result, rowIndex, 4));
      candidate["result_type"] = PQgetvalue(result, rowIndex, 5);
      try {
        candidate["args"] = json::parse(PQgetvalue(result, rowIndex, 6));
      } catch (...) {
        candidate["args"] = json::array();
      }

      json inputArgs = json::array();
      for (const json &arg : candidate["args"]) {
        std::string mode = toLower(arg.value("mode", "i"));
        if (mode == "i" || mode == "b" || mode == "v") {
          inputArgs.push_back(arg);
        }
      }
      candidate["inputArgs"] = inputArgs;
      std::string resultType = toLower(candidate.value("result_type", ""));
      candidate["setReturning"] = resultType.rfind("table(", 0) == 0 || resultType.rfind("setof ", 0) == 0 || resultType == "record";
      candidates.push_back(candidate);
    }
    PQclear(result);

    std::vector<std::string> desiredKinds = preferredKind == "proc" ? std::vector<std::string>{"p", "f"} : std::vector<std::string>{"f"};
    for (const std::string &kind : desiredKinds) {
      for (const json &candidate : candidates) {
        if (candidate.value("prokind", "") != kind) {
          continue;
        }
        int inputCount = static_cast<int>(candidate["inputArgs"].size());
        int defaultCount = candidate.value("default_count", 0);
        int minArgs = std::max(inputCount - defaultCount, 0);
        if (paramCount >= minArgs && paramCount <= inputCount) {
          return candidate;
        }
      }
    }
    return nullptr;
  }

  json normalizeRoutineParamValue(const json &rawValue, const json &argMeta) {
    std::string typeName = toLower(argMeta.value("type_name", ""));
    if (rawValue.is_null()) {
      return nullptr;
    }
    if (typeName == "json" || typeName == "jsonb") {
      if (rawValue.is_string()) {
        try {
          return json::parse(rawValue.get<std::string>());
        } catch (...) {
          return rawValue.get<std::string>();
        }
      }
      return rawValue;
    }
    if (typeName.size() >= 2 && typeName.substr(typeName.size() - 2) == "[]") {
      if (rawValue.is_array()) {
        std::vector<std::string> items;
        for (const json &item : rawValue) {
          items.push_back(stringifyValue(item));
        }
        return jsonToPgArray(items);
      }
      return rawValue;
    }
    if (typeName == "boolean") {
      std::optional<bool> parsed = parseBooleanLike(rawValue);
      return parsed.has_value() ? json(*parsed) : json(nullptr);
    }
    if (typeName == "smallint" || typeName == "integer" || typeName == "bigint") {
      std::optional<long long> parsed = parseIntegerLike(rawValue);
      return parsed.has_value() ? json(*parsed) : json(nullptr);
    }
    if (typeName == "numeric" || typeName == "real" || typeName == "double precision" || typeName == "decimal") {
      try {
        return rawValue.is_number() ? rawValue : json(std::stod(stringifyValue(rawValue)));
      } catch (...) {
        return nullptr;
      }
    }
    return rawValue.is_string() ? rawValue.get<std::string>() : stringifyValue(rawValue);
  }

  std::string buildRoutineSql(const json &routine, int providedCount, const std::string &mode) {
    json args = routine.value("inputArgs", json::array());
    std::vector<std::string> placeholders;
    for (int index = 0; index < providedCount; ++index) {
      placeholders.push_back("$" + std::to_string(index + 1) + "::" + args.at(index).value("type_name", "text"));
    }

    std::string qualifiedName = quoteIdent(routine.value("schema_name", "public")) + "." +
                                quoteIdent(routine.value("routine_name", ""));
    std::string joined = join(placeholders, ", ");
    if (mode == "call") {
      return "CALL " + qualifiedName + "(" + joined + ")";
    }
    if (mode == "select_scalar") {
      return "SELECT " + qualifiedName + "(" + joined + ") AS value";
    }
    return "SELECT * FROM " + qualifiedName + "(" + joined + ")";
  }

  json buildRoutineResponse(const json &data,
                            const std::string &sql,
                            const json &params,
                            const std::chrono::steady_clock::time_point &startedAt,
                            const json &extra) {
    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - startedAt).count();
    json result = {
        {"data", data},
        {"sl", sql},
        {"Error", nullptr},
        {"RecordsAffected", extra.value("RecordsAffected", static_cast<int>(data.is_array() ? data.size() : 0))},
        {"msec", elapsed},
        {"parms", params},
    };
    for (auto it = extra.begin(); it != extra.end(); ++it) {
      result[it.key()] = it.value();
    }
    return result;
  }
};

std::atomic<bool> gRunning(true);
int gServerSocket = -1;

void signalHandler(int) {
  gRunning.store(false);
  if (gServerSocket >= 0) {
    close(gServerSocket);
    gServerSocket = -1;
  }
}

struct HttpRequest {
  std::string method;
  std::string path;
  std::map<std::string, std::string> headers;
  std::string body;
};

HttpRequest readRequest(int clientSocket) {
  std::string buffer;
  char chunk[4096];
  std::size_t headerEnd = std::string::npos;

  while ((headerEnd = buffer.find("\r\n\r\n")) == std::string::npos) {
    ssize_t bytesRead = recv(clientSocket, chunk, sizeof(chunk), 0);
    if (bytesRead <= 0) {
      throw std::runtime_error("Failed to read request headers");
    }
    buffer.append(chunk, static_cast<std::size_t>(bytesRead));
    if (buffer.size() > 1024 * 1024) {
      throw std::runtime_error("Request headers are too large");
    }
  }

  std::string headerBlock = buffer.substr(0, headerEnd);
  std::string body = buffer.substr(headerEnd + 4);

  std::istringstream stream(headerBlock);
  std::string requestLine;
  std::getline(stream, requestLine);
  requestLine = trim(requestLine);

  HttpRequest request;
  std::istringstream requestLineStream(requestLine);
  requestLineStream >> request.method >> request.path;

  std::string line;
  while (std::getline(stream, line)) {
    line = trim(line);
    if (line.empty()) {
      continue;
    }
    std::size_t colon = line.find(':');
    if (colon == std::string::npos) {
      continue;
    }
    std::string key = toLower(trim(line.substr(0, colon)));
    std::string value = trim(line.substr(colon + 1));
    request.headers[key] = value;
  }

  int contentLength = 0;
  auto headerIt = request.headers.find("content-length");
  if (headerIt != request.headers.end()) {
    contentLength = std::max(0, std::atoi(headerIt->second.c_str()));
  }

  while (static_cast<int>(body.size()) < contentLength) {
    ssize_t bytesRead = recv(clientSocket, chunk, sizeof(chunk), 0);
    if (bytesRead <= 0) {
      throw std::runtime_error("Failed to read request body");
    }
    body.append(chunk, static_cast<std::size_t>(bytesRead));
  }

  if (static_cast<int>(body.size()) > contentLength) {
    body.resize(static_cast<std::size_t>(contentLength));
  }

  request.body = body;
  return request;
}

void sendResponse(int clientSocket, int statusCode, const json &payload) {
  std::string reason = statusCode == 200 ? "OK" : (statusCode == 404 ? "Not Found" : "Bad Request");
  std::string body = payload.dump();
  std::ostringstream stream;
  stream << "HTTP/1.1 " << statusCode << " " << reason << "\r\n";
  stream << "Content-Type: application/json; charset=utf-8\r\n";
  stream << "Content-Length: " << body.size() << "\r\n";
  stream << "Connection: close\r\n\r\n";
  stream << body;
  std::string response = stream.str();
  send(clientSocket, response.c_str(), response.size(), 0);
}

json handleHttpRequest(PgRuntime &runtime, const HttpRequest &request) {
  if (request.method == "GET" && request.path == "/health") {
    return runtime.health();
  }

  if (request.method != "POST") {
    return {
        {"ok", false},
        {"error", "Unsupported method"}};
  }

  json payload = request.body.empty() ? json::object() : json::parse(request.body);
  std::string action = toLower(payload.value("action", ""));

  if (action == "read") {
    return runtime.handleRead(payload);
  }
  if (action == "save") {
    return runtime.handleSave(payload);
  }
  if (action == "delete") {
    return runtime.handleDelete(payload);
  }
  if (action == "routine") {
    return runtime.handleRoutine(payload);
  }

  throw std::runtime_error("Unknown action: " + action);
}

} // namespace

int main() {
  std::signal(SIGINT, signalHandler);
  std::signal(SIGTERM, signalHandler);

  const char *host = envOrDefault("CPP_CORE_HOST", "127.0.0.1");
  int port = std::atoi(envOrDefault("CPP_CORE_PORT", "3012"));
  if (port <= 0) {
    port = 3012;
  }

  int serverSocket = socket(AF_INET, SOCK_STREAM, 0);
  if (serverSocket < 0) {
    std::cerr << "Failed to create socket: " << std::strerror(errno) << std::endl;
    return 1;
  }

  int reuse = 1;
  setsockopt(serverSocket, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));

  sockaddr_in address {};
  address.sin_family = AF_INET;
  address.sin_port = htons(static_cast<uint16_t>(port));
  if (inet_pton(AF_INET, host, &address.sin_addr) != 1) {
    std::cerr << "Invalid CPP_CORE_HOST: " << host << std::endl;
    close(serverSocket);
    return 1;
  }

  if (bind(serverSocket, reinterpret_cast<sockaddr *>(&address), sizeof(address)) < 0) {
    std::cerr << "Failed to bind socket: " << std::strerror(errno) << std::endl;
    close(serverSocket);
    return 1;
  }

  if (listen(serverSocket, 32) < 0) {
    std::cerr << "Failed to listen on socket: " << std::strerror(errno) << std::endl;
    close(serverSocket);
    return 1;
  }

  gServerSocket = serverSocket;
  PgRuntime runtime;
  std::cout << "[quantum-core] listening on http://" << host << ":" << port << std::endl;

  while (gRunning.load()) {
    sockaddr_in clientAddress {};
    socklen_t clientLength = sizeof(clientAddress);
    int clientSocket = accept(serverSocket, reinterpret_cast<sockaddr *>(&clientAddress), &clientLength);
    if (clientSocket < 0) {
      if (!gRunning.load()) {
        break;
      }
      if (errno == EINTR) {
        continue;
      }
      std::cerr << "Accept failed: " << std::strerror(errno) << std::endl;
      continue;
    }

    try {
      HttpRequest request = readRequest(clientSocket);
      json payload = handleHttpRequest(runtime, request);
      sendResponse(clientSocket, 200, payload);
    } catch (const std::exception &error) {
      sendResponse(clientSocket, 400, {{"ok", false}, {"error", error.what()}});
    }

    close(clientSocket);
  }

  close(serverSocket);
  gServerSocket = -1;
  return 0;
}
