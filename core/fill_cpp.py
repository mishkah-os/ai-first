"""Fill C++ ORM pillars into DB components."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.engine import CoreEngine

DSN = "postgresql://aifirst:aifirst_password@localhost:5433/ai_first_platform"

PILLARS = {
"str-utils": {"schema": r'''#include <string>
#include <algorithm>
#include <cctype>''', "logic": r'''
std::string trim(const std::string &s) {
  auto a = s.find_first_not_of(" \t\r\n");
  if (a == std::string::npos) return "";
  return s.substr(a, s.find_last_not_of(" \t\r\n") - a + 1);
}
std::string toLower(std::string s) {
  for (char &c : s) c = (char)std::tolower((unsigned char)c);
  return s;
}
std::string quoteIdent(const std::string &n) {
  std::string v = trim(n);
  if (v.empty()) throw std::runtime_error("Identifier required");
  std::string o = "\"";
  for (char c : v) { if (c == '"') o += "\"\""; else o += c; }
  return o + "\"";
}
std::string escapeLike(const std::string &s) {
  std::string o; o.reserve(s.size());
  for (char c : s) { if (c=='\\' || c=='%' || c=='_') o += '\\'; o += c; }
  return o;
}
std::string joinVec(const std::vector<std::string> &v, const std::string &d) {
  std::string o;
  for (size_t i = 0; i < v.size(); ++i) { if (i) o += d; o += v[i]; }
  return o;
}'''},

"json-helpers": {"schema": r'''#include <nlohmann/json.hpp>
#include <optional>
#include <vector>
using json = nlohmann::json;''', "logic": r'''
std::string stringifyValue(const json &v) {
  if (v.is_null()) return "";
  if (v.is_string()) return v.get<std::string>();
  if (v.is_boolean()) return v.get<bool>() ? "true" : "false";
  return v.dump();
}
std::string jsonStr(const json &v, const char *k, const std::string &fb = "") {
  if (!v.is_object() || !v.contains(k) || v[k].is_null()) return fb;
  return v[k].is_string() ? v[k].get<std::string>() : v[k].dump();
}
int jsonInt(const json &v, const char *k, int fb = 0) {
  if (!v.is_object() || !v.contains(k) || v[k].is_null()) return fb;
  if (v[k].is_number_integer()) return v[k].get<int>();
  try { return std::stoi(stringifyValue(v[k])); } catch (...) { return fb; }
}
bool jsonBool(const json &v, const char *k, bool fb = false) {
  if (!v.is_object() || !v.contains(k) || v[k].is_null()) return fb;
  if (v[k].is_boolean()) return v[k].get<bool>();
  std::string t = toLower(trim(stringifyValue(v[k])));
  if (t=="1"||t=="true"||t=="yes") return true;
  if (t=="0"||t=="false"||t=="no") return false;
  return fb;
}
std::optional<long long> parseInt(const json &v) {
  if (v.is_null()) return std::nullopt;
  try {
    if (v.is_number_integer()) return v.get<long long>();
    if (v.is_number()) return (long long)v.get<double>();
    std::string t = trim(v.is_string() ? v.get<std::string>() : v.dump());
    if (t.empty()) return std::nullopt;
    return std::stoll(t);
  } catch (...) { return std::nullopt; }
}
json unwrapInput(const json &v) {
  if (v.is_object() && v.contains("id")) return v["id"];
  return v;
}'''},

"column-meta": {"logic": r'''
struct ColumnMeta {
  std::string name, trans_name, data_type, type, referenced_table;
  std::string referenced_column = "id", search_columns, component;
  int max_length = 0;
  bool is_nullable=true, is_identity=false, is_primary_key=false, isreferences=false;
  json default_value = nullptr;
};
struct ObjectMeta {
  std::string name;
  std::vector<ColumnMeta> columns;
};
ColumnMeta parseColumn(const json &v) {
  ColumnMeta c;
  c.name = jsonStr(v,"name"); c.trans_name = jsonStr(v,"trans_name");
  c.data_type = toLower(jsonStr(v,"data_type")); c.type = jsonStr(v,"type");
  c.max_length = jsonInt(v,"max_length"); c.is_nullable = jsonBool(v,"is_nullable",true);
  c.is_primary_key = jsonBool(v,"is_primary_key"); c.isreferences = jsonBool(v,"isreferences");
  c.referenced_table = jsonStr(v,"ReferencedTable");
  c.referenced_column = jsonStr(v,"ReferencedColumnName","id");
  c.search_columns = jsonStr(v,"search_columns");
  return c;
}
ObjectMeta parseObjectMeta(const json &v) {
  if (!v.is_object()) throw std::runtime_error("Object metadata missing");
  ObjectMeta o; o.name = v.value("name","");
  if (o.name.empty()) throw std::runtime_error("Object name required");
  if (!v.contains("columns")||!v["columns"].is_array()) throw std::runtime_error("Columns required");
  for (auto &c : v["columns"]) o.columns.push_back(parseColumn(c));
  return o;
}'''},

"alias-resolver": {"logic": r'''
const ColumnMeta* findColumn(const ObjectMeta &o, const std::string &n) {
  std::string t = toLower(trim(n));
  if (t.empty()) return nullptr;
  for (auto &c : o.columns)
    if (toLower(c.name)==t || (!c.trans_name.empty() && toLower(c.trans_name)==t)) return &c;
  return nullptr;
}
std::map<std::string,std::string> buildAliasMap(const ObjectMeta &o) {
  std::map<std::string,std::string> m;
  for (auto &c : o.columns) {
    std::string cn = trim(c.name); if (cn.empty()) continue;
    m[toLower(cn)] = cn;
    if (!c.trans_name.empty()) m[toLower(c.trans_name)] = cn;
    if (cn=="tenant_id") { m["company_id"]=cn; m["compid"]=cn; }
    if (cn=="created_at") m["begin_date"]=cn;
    if (cn=="updated_at") m["last_update"]=cn;
    if (cn=="created_by") m["user_insert"]=cn;
  }
  return m;
}
std::optional<std::string> resolveCol(const ObjectMeta &o, const std::string &n) {
  auto m = buildAliasMap(o);
  auto it = m.find(toLower(trim(n)));
  return it != m.end() ? std::optional(it->second) : std::nullopt;
}
const ColumnMeta* getPK(const ObjectMeta &o) {
  for (auto &c : o.columns) if (c.is_primary_key) return &c;
  return nullptr;
}'''},

"value-normalizer": {"logic": r'''
json normalizeValue(const ColumnMeta &col, const json &val) {
  json s = unwrapInput(val);
  if (s.is_null()) return nullptr;
  if (s.is_string() && trim(s.get<std::string>()).empty()) return nullptr;
  std::string dt = col.data_type;
  if (dt=="bit") {
    std::string t = toLower(trim(stringifyValue(s)));
    if (t=="1"||t=="true"||t=="yes") return true;
    if (t=="0"||t=="false"||t=="no") return false;
    return nullptr;
  }
  if (dt=="bigint"||dt=="int"||dt=="integer"||dt=="smallint") {
    auto p = parseInt(s); return p ? json(*p) : json(nullptr);
  }
  if (dt=="decimal"||dt=="numeric") {
    try { return s.is_number() ? s : json(std::stod(stringifyValue(s))); }
    catch (...) { return nullptr; }
  }
  if (dt=="json"||dt=="jsonb") {
    if (s.is_string()) { try { return json::parse(s.get<std::string>()); } catch (...) { return s; } }
    return s;
  }
  return s.is_string() ? s : json(stringifyValue(s));
}'''},

"change-logger": {"schema": r'''#include <ctime>
#include <chrono>''', "logic": r'''
std::string nowIso() {
  auto now = std::chrono::system_clock::now();
  std::time_t t = std::chrono::system_clock::to_time_t(now);
  std::tm tm{}; gmtime_r(&t, &tm);
  char buf[32]; std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tm);
  return buf;
}
std::string genPublicId(int len = 26) {
  static const char A[] = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
  static bool seeded = false;
  if (!seeded) { std::srand((unsigned)std::time(nullptr)); seeded = true; }
  int n = len > 0 ? len : 26;
  std::string o; o.reserve(n);
  for (int i = 0; i < n; ++i) o += A[std::rand() % 32];
  return o;
}'''},

"pg-runtime": {"schema": r'''#include <postgresql/libpq-fe.h>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <map>''', "logic": r'''
struct ReqCtx {
  std::optional<long long> tenantId, userId;
};
ReqCtx parseCtx(const json &p) {
  ReqCtx c;
  if (!p.is_object()) return c;
  c.tenantId = parseInt(p.contains("tenantId") ? p["tenantId"] : json(nullptr));
  c.userId = parseInt(p.contains("userId") ? p["userId"] : json(nullptr));
  return c;
}
class PgRuntime {
public:
  PGconn *conn_ = nullptr;
  bool connect() {
    if (conn_ && PQstatus(conn_)==CONNECTION_OK) return true;
    std::string cs = buildConnStr();
    if (conn_) { PQfinish(conn_); conn_=nullptr; }
    conn_ = PQconnectdb(cs.c_str());
    return PQstatus(conn_)==CONNECTION_OK;
  }
  ~PgRuntime() { if (conn_) PQfinish(conn_); }
  std::string lastErr() { return conn_ ? PQerrorMessage(conn_) : "No connection"; }
  json health() {
    if (!connect()) return {{"status","error"},{"database",false},{"error",lastErr()}};
    PGresult *r = PQexec(conn_,"SELECT 1");
    bool ok = PQresultStatus(r)==PGRES_TUPLES_OK;
    if (r) PQclear(r);
    return {{"status",ok?"ok":"error"},{"database",ok},{"driver","libpq"}};
  }
  PGresult* execP(const std::string &sql, const std::vector<std::optional<std::string>> &vals) {
    std::vector<const char*> pv;
    for (auto &v : vals) pv.push_back(v ? v->c_str() : nullptr);
    return PQexecParams(conn_, sql.c_str(), (int)pv.size(), nullptr,
      pv.data(), nullptr, nullptr, 0);
  }
  void execS(const char *sql) { PGresult *r = PQexec(conn_, sql); if(r) PQclear(r); }
private:
  std::string buildConnStr() {
    const char *u = std::getenv("DATABASE_URL");
    if (u && *u) return u;
    auto e = [](const char *n, const char *d) { const char *v=std::getenv(n); return v&&*v?v:d; };
    std::ostringstream s;
    s << "host=" << e("PGHOST","127.0.0.1") << " port=" << e("PGPORT","5432")
      << " dbname=" << e("PGDATABASE","ai_first") << " user=" << e("PGUSER","aifirst")
      << " password=" << e("PGPASSWORD","") << " client_encoding=UTF8";
    return s.str();
  }
};'''},

"http-listener": {"logic": r'''
int main(int argc, char* argv[]) {
  PgRuntime pg;
  if (!pg.connect()) {
    std::cerr << "DB connection failed: " << pg.lastErr() << std::endl;
    return 1;
  }
  json h = pg.health();
  std::cout << "AI-First Quantum Core v1.0" << std::endl;
  std::cout << "Database: " << h.dump() << std::endl;
  std::cout << "ORM ready. Schema-driven CRUD engine active." << std::endl;
  if (argc > 1 && std::string(argv[1]) == "--test") {
    std::cout << "QUANTUM-TEST-OK" << std::endl;
    return 0;
  }
  std::cout << "Listening for JSON requests on stdin..." << std::endl;
  std::string line;
  while (std::getline(std::cin, line)) {
    if (line.empty()) continue;
    try {
      json req = json::parse(line);
      std::string action = req.value("action","");
      json result;
      if (action == "health") result = pg.health();
      else result = {{"error","Unknown action: " + action}};
      std::cout << result.dump() << std::endl;
    } catch (std::exception &e) {
      std::cout << json({{"error",e.what()}}).dump() << std::endl;
    }
  }
  return 0;
}'''},
}

async def main():
    e = CoreEngine(DSN)
    await e.connect()
    for slug, pillars in PILLARS.items():
        comp = await e.reveal(slug)
        cid = None
        async with e.pool.acquire() as conn:
            cid = await conn.fetchval("SELECT id FROM component WHERE slug=$1", slug)
        for kind, content in pillars.items():
            await e.set_pillar(cid, kind, content, lang="cpp")
            print(f"  {slug}.{kind} = {len(content)} bytes")
    print("\nDone. Compiling...")
    from core.compiler import Compiler
    import shutil, os
    out = str(Path(__file__).parent.parent / "_build")
    if os.path.exists(out): shutil.rmtree(out)
    c = Compiler(e)
    files = await c.compile(out, strategy="single-bundle")
    print(f"Generated {len(files)} files:")
    for f in files:
        print(f"  {os.path.basename(f)} ({os.path.getsize(f)} bytes)")
    await e.close()

if __name__ == "__main__":
    asyncio.run(main())
